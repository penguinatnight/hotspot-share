from pathlib import Path
from setuptools import setup, find_packages

web_files = [str(p) for p in Path("web").glob("*") if p.is_file()]

setup(
    name="hotspot-share",
    version="2.0.17",
    description="High-Speed Local Wi-Fi File Sharing & Multimodal Clipboard Sync",
    author="penguinatnight", author_email="penguinatnight1@gmail.com", url="https://github.com/penguinatnight/hotspot-share",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"hotspot_share": ["web/*"]},
    include_package_data=True,
    data_files=[
        ("share/hotspot-share/web", web_files),
    ],
    entry_points={
        "console_scripts": [
            "hotspot-share = hotspot_share.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Topic :: Communications :: File Sharing",
        "Topic :: Utilities",
    ],
)
