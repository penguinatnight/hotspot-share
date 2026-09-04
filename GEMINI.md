# Hotspot Share (`hotspot-share`)

High-throughput local Wi-Fi file sharing and bi-directional clipboard sync between Linux desktops and mobile phones (zero cloud, zero phone app needed).

## Tech Stack
- Python 3 standard library (zero external Python dependencies), WebKitGTK desktop interface, NetworkManager AP automation.
- Debian/Ubuntu packaging (`debian/`, `snap/`).

## Key Structure
- `app.py`: Main launcher.
- `src/`: HTTP micro-server, 8MB chunked transfer engine, clipboard sync hooks.
- `gui/`: WebKitGTK desktop user interface.

## Environment & Execution
- **Environment**: Standard Python 3 system environment.
- **Scope Boundaries**: Confine file exploration and operations strictly to this project directory.
