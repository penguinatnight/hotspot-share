#include <gtk/gtk.h>
#include <webkit2/webkit2.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <signal.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <errno.h>
#include <string.h>

#define DEFAULT_PORT 8080
#define MAX_PORT_ATTEMPTS 20

static pid_t server_pid = 0;
static int active_port = DEFAULT_PORT;
static char server_url[256] = "http://127.0.0.1:8080";
static GtkWidget *main_window = NULL;
static GtkStatusIcon *tray_icon = NULL;

static int check_socket(int port) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return 0;

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);
    inet_pton(AF_INET, "127.0.0.1", &serv_addr.sin_addr);

    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 80000; // 80ms timeout
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&tv, sizeof tv);

    int res = connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr));
    close(sock);
    return (res == 0);
}

static char *get_runtime_json_path(void) {
    const char *xdg_runtime = getenv("XDG_RUNTIME_DIR");
    char *path = malloc(512);
    if (!path) return NULL;
    if (xdg_runtime && strlen(xdg_runtime) > 0) {
        snprintf(path, 512, "%s/hotspot-share/server.json", xdg_runtime);
    } else {
        snprintf(path, 512, "/tmp/hotspot-share-runtime-%u/hotspot-share/server.json", (unsigned int)getuid());
    }
    return path;
}

static int is_hotspot_process(pid_t pid) {
    if (pid <= 1 || pid == getpid()) return 0;
    char path[64];
    snprintf(path, sizeof(path), "/proc/%d/cmdline", (int)pid);
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char cmdline[512];
    size_t n = fread(cmdline, 1, sizeof(cmdline) - 1, f);
    fclose(f);
    if (n <= 0) return 0;
    cmdline[n] = '\0';
    for (size_t i = 0; i < n; i++) {
        if (cmdline[i] == '\0') cmdline[i] = ' ';
    }
    if (strstr(cmdline, "hotspot-share") != NULL || strstr(cmdline, "hotspot_share") != NULL) {
        return 1;
    }
    return 0;
}

static int read_port_from_runtime(void) {
    char *json_path = get_runtime_json_path();
    FILE *f = fopen(json_path, "r");
    free(json_path);
    if (!f) return 0;

    char buffer[1024];
    size_t bytes = fread(buffer, 1, sizeof(buffer) - 1, f);
    fclose(f);
    buffer[bytes] = '\0';

    char *port_key = strstr(buffer, "\"port\":");
    if (port_key) {
        int p = atoi(port_key + 7);
        if (p > 0 && p < 65536) {
            return p;
        }
    }
    return 0;
}

static int read_pid_from_runtime(void) {
    char *json_path = get_runtime_json_path();
    FILE *f = fopen(json_path, "r");
    free(json_path);
    if (!f) return 0;

    char buffer[1024];
    size_t bytes = fread(buffer, 1, sizeof(buffer) - 1, f);
    fclose(f);
    buffer[bytes] = '\0';

    char *pid_key = strstr(buffer, "\"pid\":");
    if (pid_key) {
        int pid = atoi(pid_key + 6);
        if (pid > 0) {
            return pid;
        }
    }
    return 0;
}

static int check_server_healthy(int port) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return 0;

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);
    inet_pton(AF_INET, "127.0.0.1", &serv_addr.sin_addr);

    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 250000; // 250ms timeout
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&tv, sizeof tv);

    if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) != 0) {
        close(sock);
        return 0;
    }

    const char *req = "GET / HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    send(sock, req, strlen(req), 0);

    char resp[2048];
    memset(resp, 0, sizeof(resp));
    int n = recv(sock, resp, sizeof(resp) - 1, 0);
    close(sock);

    if (n <= 0) return 0;

    // Must be HTTP 200 and must NOT contain "Web frontend missing"
    if (strstr(resp, "200 OK") != NULL && strstr(resp, "Web frontend missing") == NULL) {
        return 1;
    }

    return 0;
}

static GdkPixbuf *find_app_icon(void) {
    // 1. Try GTK Icon Theme
    GtkIconTheme *theme = gtk_icon_theme_get_default();
    if (gtk_icon_theme_has_icon(theme, "hotspot-share")) {
        return gtk_icon_theme_load_icon(theme, "hotspot-share", 512, 0, NULL);
    }

    // 2. Check XDG & Snap data directories
    const char *candidates[] = {
        "/usr/share/icons/hicolor/512x512/apps/hotspot-share.png",
        "/usr/local/share/icons/hicolor/512x512/apps/hotspot-share.png",
        NULL
    };

    for (int i = 0; candidates[i] != NULL; i++) {
        if (access(candidates[i], R_OK) == 0) {
            return gdk_pixbuf_new_from_file(candidates[i], NULL);
        }
    }

    // 3. Check user local directory
    const char *home = getenv("HOME");
    if (home) {
        char user_path[512];
        snprintf(user_path, sizeof(user_path), "%s/.local/share/icons/hicolor/512x512/apps/hotspot-share.png", home);
        if (access(user_path, R_OK) == 0) {
            return gdk_pixbuf_new_from_file(user_path, NULL);
        }
    }

    // 4. Check SNAP directory
    const char *snap = getenv("SNAP");
    if (snap) {
        char snap_path[512];
        snprintf(snap_path, sizeof(snap_path), "%s/share/icons/hicolor/512x512/apps/hotspot-share.png", snap);
        if (access(snap_path, R_OK) == 0) {
            return gdk_pixbuf_new_from_file(snap_path, NULL);
        }
    }

    return NULL;
}

static void start_backend_server(int req_port) {
    // 1. Check if runtime file or port is already alive with a HEALTHY frontend
    int p = read_port_from_runtime();
    if (p > 0 && check_server_healthy(p)) {
        active_port = p;
        snprintf(server_url, sizeof(server_url), "http://127.0.0.1:%d", active_port);
        return;
    }

    if (check_server_healthy(req_port)) {
        active_port = req_port;
        snprintf(server_url, sizeof(server_url), "http://127.0.0.1:%d", active_port);
        return;
    }

    // 2. If port is occupied by a stale zombie server (failed health check), terminate it
    if (check_socket(req_port)) {
        int stale_pid = read_pid_from_runtime();
        if (stale_pid > 0 && stale_pid != getpid() && is_hotspot_process(stale_pid)) {
            kill(stale_pid, SIGTERM);
            usleep(150000); // 150ms
            if (check_socket(req_port) && is_hotspot_process(stale_pid)) {
                kill(stale_pid, SIGKILL);
                usleep(150000); // 150ms
            }
        }
        // If still occupied, pick an alternate port
        if (check_socket(req_port)) {
            for (int candidate = req_port + 1; candidate < req_port + MAX_PORT_ATTEMPTS; candidate++) {
                if (!check_socket(candidate)) {
                    req_port = candidate;
                    break;
                }
            }
        }
    }

    server_pid = fork();
    if (server_pid == 0) {
        #ifdef __linux__
        prctl(PR_SET_PDEATHSIG, SIGTERM);
        #endif

        char port_str[16];
        snprintf(port_str, sizeof(port_str), "%d", req_port);

        // Check if installed as 'hotspot-share' binary
        char *exec_args[] = {
            "hotspot-share",
            "-p", port_str,
            "--no-qr",
            NULL
        };
        execvp("hotspot-share", exec_args);

        // Fallback: search Python module in current / standard paths
        char *python_args[] = {
            "python3",
            "-m", "hotspot_share.cli",
            "-p", port_str,
            "--no-qr",
            NULL
        };
        execvp("python3", python_args);
        _exit(1);
    }

    // Wait up to 3 seconds for server to become responsive and pass health check
    for (int i = 0; i < 60; i++) {
        usleep(50000); // 50ms
        int dyn_p = read_port_from_runtime();
        if (dyn_p > 0 && check_server_healthy(dyn_p)) {
            active_port = dyn_p;
            snprintf(server_url, sizeof(server_url), "http://127.0.0.1:%d", active_port);
            return;
        }
        if (check_server_healthy(req_port)) {
            active_port = req_port;
            snprintf(server_url, sizeof(server_url), "http://127.0.0.1:%d", active_port);
            return;
        }
    }

    snprintf(server_url, sizeof(server_url), "http://127.0.0.1:%d", req_port);
}

static void on_tray_activate(GtkStatusIcon *status_icon, gpointer user_data) {
    if (gtk_widget_get_visible(main_window)) {
        gtk_widget_hide(main_window);
    } else {
        gtk_window_present(GTK_WINDOW(main_window));
    }
}

static void stop_backend_server(void) {
    if (server_pid <= 0) return;
    pid_t pid = server_pid;
    server_pid = -1;

    kill(pid, SIGTERM);

    // Wait up to 1.5 seconds for graceful shutdown
    for (int i = 0; i < 15; i++) {
        int status;
        pid_t res = waitpid(pid, &status, WNOHANG);
        if (res == pid || res == -1) {
            return;
        }
        g_usleep(100000); // 100ms
    }

    // Force kill if still running
    kill(pid, SIGKILL);
    int status;
    waitpid(pid, &status, 0);
}

static void on_tray_quit(GtkWidget *widget, gpointer data) {
    stop_backend_server();
    gtk_main_quit();
}

static void on_tray_popup_menu(GtkStatusIcon *status_icon, guint button, guint activate_time, gpointer user_data) {
    GtkWidget *menu = gtk_menu_new();

    GtkWidget *item_open = gtk_menu_item_new_with_label("Open Hotspot Share");
    g_signal_connect_swapped(item_open, "activate", G_CALLBACK(gtk_window_present), main_window);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item_open);

    GtkWidget *item_sep = gtk_separator_menu_item_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item_sep);

    GtkWidget *item_quit = gtk_menu_item_new_with_label("Quit Hotspot Share");
    g_signal_connect(item_quit, "activate", G_CALLBACK(on_tray_quit), NULL);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item_quit);

    gtk_widget_show_all(menu);
    gtk_menu_popup(GTK_MENU(menu), NULL, NULL, gtk_status_icon_position_menu, status_icon, button, activate_time);
}

static void on_window_destroy(GtkWidget *widget, gpointer data) {
    stop_backend_server();
    gtk_main_quit();
}

static gboolean on_window_delete(GtkWidget *widget, GdkEvent *event, gpointer data) {
    // If tray is active, minimize to tray instead of quitting
    if (tray_icon && gtk_status_icon_is_embedded(tray_icon)) {
        gtk_widget_hide(widget);
        return TRUE; // Handled
    }
    return FALSE; // Proceed with destroy
}

static gboolean on_load_failed(WebKitWebView *web_view, WebKitLoadEvent load_event, gchar *failing_uri, GError *error, gpointer user_data) {
    fprintf(stderr, "[HotspotShare GUI] WebKit load failed for %s: %s\n", failing_uri, error ? error->message : "unknown");
    return FALSE;
}

static gboolean is_internal_server_uri(const gchar *uri) {
    if (!uri) return FALSE;
    if (server_url[0] && g_str_has_prefix(uri, server_url)) {
        char next = uri[strlen(server_url)];
        if (next == '\0' || next == '/' || next == '?' || next == '#') return TRUE;
    }
    char expected_prefix[64];
    snprintf(expected_prefix, sizeof(expected_prefix), "http://127.0.0.1:%d", active_port);
    if (g_str_has_prefix(uri, expected_prefix)) {
        char next = uri[strlen(expected_prefix)];
        if (next == '\0' || next == '/' || next == '?' || next == '#') return TRUE;
    }
    snprintf(expected_prefix, sizeof(expected_prefix), "http://localhost:%d", active_port);
    if (g_str_has_prefix(uri, expected_prefix)) {
        char next = uri[strlen(expected_prefix)];
        if (next == '\0' || next == '/' || next == '?' || next == '#') return TRUE;
    }
    return FALSE;
}

static void on_download_decide_destination(WebKitDownload *download, gchar *suggested_filename, gpointer user_data) {
    const char *home = getenv("HOME");
    char dest_dir[512];
    char dest_path[1024];
    if (home && strlen(home) > 0) {
        snprintf(dest_dir, sizeof(dest_dir), "%s/Desktop/from-phone", home);
        g_mkdir_with_parents(dest_dir, 0755);
        snprintf(dest_path, sizeof(dest_path), "%s/%s", dest_dir, (suggested_filename && strlen(suggested_filename) > 0) ? suggested_filename : "download");
    } else {
        snprintf(dest_path, sizeof(dest_path), "/tmp/%s", (suggested_filename && strlen(suggested_filename) > 0) ? suggested_filename : "download");
    }
    gchar *dest_uri = g_filename_to_uri(dest_path, NULL, NULL);
    if (dest_uri) {
        webkit_download_set_destination(download, dest_uri);
        webkit_download_set_allow_overwrite(download, TRUE);
        g_free(dest_uri);
    }
}

static void on_download_started(WebKitWebContext *context, WebKitDownload *download, gpointer user_data) {
    g_signal_connect(download, "decide-destination", G_CALLBACK(on_download_decide_destination), NULL);
}

static gboolean on_decide_policy(WebKitWebView *web_view, WebKitPolicyDecision *decision, WebKitPolicyDecisionType type, gpointer user_data) {
    if (type == WEBKIT_POLICY_DECISION_TYPE_RESPONSE) {
        WebKitResponsePolicyDecision *r_decision = WEBKIT_RESPONSE_POLICY_DECISION(decision);
        if (!webkit_response_policy_decision_is_mime_type_supported(r_decision)) {
            webkit_policy_decision_download(decision);
            return TRUE;
        }
        return FALSE;
    }
    if (type == WEBKIT_POLICY_DECISION_TYPE_NAVIGATION_ACTION || type == WEBKIT_POLICY_DECISION_TYPE_NEW_WINDOW_ACTION) {
        WebKitNavigationPolicyDecision *nav_decision = WEBKIT_NAVIGATION_POLICY_DECISION(decision);
        WebKitNavigationAction *action = webkit_navigation_policy_decision_get_navigation_action(nav_decision);
        WebKitURIRequest *request = webkit_navigation_action_get_request(action);
        const gchar *uri = webkit_uri_request_get_uri(request);
        if (uri) {
            if (is_internal_server_uri(uri)) {
                return FALSE;
            }
            if (g_str_has_prefix(uri, "http://") || g_str_has_prefix(uri, "https://") || g_str_has_prefix(uri, "mailto:")) {
                gtk_show_uri_on_window(GTK_WINDOW(main_window), uri, GDK_CURRENT_TIME, NULL);
            }
            webkit_policy_decision_ignore(decision);
            return TRUE;
        }
    }
    return FALSE;
}

static gboolean on_webview_event(GtkWidget *widget, GdkEvent *event, gpointer user_data) {
    if (event->type == GDK_TOUCHPAD_PINCH) {
        // Prevent trackpad pinch-to-zoom gesture completely
        return TRUE;
    }
    if (event->type == GDK_SCROLL) {
        GdkEventScroll *scroll = (GdkEventScroll *)event;
        if (scroll->state & GDK_CONTROL_MASK) {
            // Prevent Ctrl+scroll zoom
            return TRUE;
        }
    }
    if (event->type == GDK_KEY_PRESS) {
        GdkEventKey *key = (GdkEventKey *)event;
        if (key->state & GDK_CONTROL_MASK) {
            if (key->keyval == GDK_KEY_plus || key->keyval == GDK_KEY_equal ||
                key->keyval == GDK_KEY_minus || key->keyval == GDK_KEY_underscore ||
                key->keyval == GDK_KEY_0 || key->keyval == GDK_KEY_KP_Add ||
                key->keyval == GDK_KEY_KP_Subtract || key->keyval == GDK_KEY_KP_0) {
                return TRUE; // Block Ctrl+zoom keyboard shortcuts
            }
        }
    }
    return FALSE;
}

static gboolean on_webview_scroll(GtkWidget *widget, GdkEventScroll *event, gpointer user_data) {
    if (event->state & GDK_CONTROL_MASK) {
        // Prevent trackpad Ctrl+scroll pinch zoom
        return TRUE;
    }
    return FALSE;
}

static void on_webview_zoom_level_changed(WebKitWebView *web_view, GParamSpec *pspec, gpointer user_data) {
    static gboolean in_reset = FALSE;
    if (in_reset) return;
    double level = webkit_web_view_get_zoom_level(web_view);
    if (level != 1.0) {
        in_reset = TRUE;
        webkit_web_view_set_zoom_level(web_view, 1.0);
        in_reset = FALSE;
    }
}

int main(int argc, char *argv[]) {
    g_set_prgname("hotspot-share");
    g_set_application_name("Hotspot Share");
    signal(SIGCHLD, SIG_IGN);
    setenv("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1", 1);
    setenv("GIO_USE_NETWORK_MONITOR", "base", 1);
    setenv("NO_AT_BRIDGE", "1", 1);

    gtk_init(&argc, &argv);

    int req_port = DEFAULT_PORT;
    for (int i = 1; i < argc; i++) {
        if ((strcmp(argv[i], "-p") == 0 || strcmp(argv[i], "--port") == 0) && i + 1 < argc) {
            req_port = atoi(argv[i + 1]);
            if (req_port <= 0) req_port = DEFAULT_PORT;
        }
    }

    GdkPixbuf *app_icon = find_app_icon();
    if (app_icon) {
        gtk_window_set_default_icon(app_icon);
    }

    start_backend_server(req_port);

    main_window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(main_window), "Hotspot Share");
    gtk_window_set_default_size(GTK_WINDOW(main_window), 980, 860);
    gtk_widget_set_size_request(main_window, 720, 540);
    GdkGeometry hints;
    memset(&hints, 0, sizeof(hints));
    hints.min_width = 720;
    hints.min_height = 540;
    gtk_window_set_geometry_hints(GTK_WINDOW(main_window), NULL, &hints, GDK_HINT_MIN_SIZE);
    gtk_window_set_position(GTK_WINDOW(main_window), GTK_WIN_POS_CENTER);
    gtk_window_set_wmclass(GTK_WINDOW(main_window), "hotspot-share", "hotspot-share");

    if (app_icon) {
        gtk_window_set_icon(GTK_WINDOW(main_window), app_icon);
    }

    // Status Tray Indicator
    tray_icon = gtk_status_icon_new();
    if (app_icon) {
        gtk_status_icon_set_from_pixbuf(tray_icon, app_icon);
    } else {
        gtk_status_icon_set_from_icon_name(tray_icon, "network-wireless");
    }
    gtk_status_icon_set_tooltip_text(tray_icon, "Hotspot Share - File Transfer & Clipboard Sync");
    g_signal_connect(tray_icon, "activate", G_CALLBACK(on_tray_activate), NULL);
    g_signal_connect(tray_icon, "popup-menu", G_CALLBACK(on_tray_popup_menu), NULL);
    gtk_status_icon_set_visible(tray_icon, TRUE);

    g_signal_connect(main_window, "delete-event", G_CALLBACK(on_window_delete), NULL);
    g_signal_connect(main_window, "destroy", G_CALLBACK(on_window_destroy), NULL);

    WebKitSettings *settings = webkit_settings_new();
    webkit_settings_set_enable_developer_extras(settings, TRUE);
    webkit_settings_set_hardware_acceleration_policy(settings, WEBKIT_HARDWARE_ACCELERATION_POLICY_ON_DEMAND);
    webkit_settings_set_enable_smooth_scrolling(settings, TRUE);
    webkit_settings_set_enable_javascript_markup(settings, TRUE);
    webkit_settings_set_enable_media_stream(settings, TRUE);
    webkit_settings_set_enable_mediasource(settings, TRUE);
    webkit_settings_set_javascript_can_access_clipboard(settings, TRUE);

    GtkWidget *web_view = webkit_web_view_new_with_settings(settings);
    g_signal_connect(web_view, "load-failed", G_CALLBACK(on_load_failed), NULL);
    g_signal_connect(web_view, "decide-policy", G_CALLBACK(on_decide_policy), NULL);
    
    // Enforce fixed 1.0 zoom level and block trackpad pinch zoom for native desktop feel
    webkit_web_view_set_zoom_level(WEBKIT_WEB_VIEW(web_view), 1.0);
    gtk_widget_add_events(web_view, GDK_SCROLL_MASK | GDK_TOUCHPAD_GESTURE_MASK | GDK_TOUCH_MASK | GDK_KEY_PRESS_MASK);
    g_signal_connect(web_view, "event", G_CALLBACK(on_webview_event), NULL);
    g_signal_connect(web_view, "scroll-event", G_CALLBACK(on_webview_scroll), NULL);
    g_signal_connect(web_view, "notify::zoom-level", G_CALLBACK(on_webview_zoom_level_changed), NULL);
    
    // Disable stale disk caching so user always sees the latest live UI
    WebKitWebContext *web_context = webkit_web_view_get_context(WEBKIT_WEB_VIEW(web_view));
    if (web_context) {
        g_signal_connect(web_context, "download-started", G_CALLBACK(on_download_started), NULL);
        webkit_web_context_set_cache_model(web_context, WEBKIT_CACHE_MODEL_DOCUMENT_VIEWER);
        webkit_web_context_clear_cache(web_context);
        webkit_web_context_set_network_proxy_settings(web_context, WEBKIT_NETWORK_PROXY_MODE_NO_PROXY, NULL);
    }

    GdkRGBA bg_color = { 0.05, 0.07, 0.09, 1.0 };
    webkit_web_view_set_background_color(WEBKIT_WEB_VIEW(web_view), &bg_color);

    webkit_web_view_load_uri(WEBKIT_WEB_VIEW(web_view), server_url);

    gtk_container_add(GTK_CONTAINER(main_window), web_view);
    gtk_widget_show_all(main_window);

    gtk_main();

    return 0;
}
