from setuptools import setup, find_packages

setup(
    name="hotspot-share",
    version="2.0.0",
    description="High-Speed Local Wi-Fi File Sharing & Multimodal Clipboard Sync",
    author="Yeabsra Henok", author_email="yeabsrahenok0909@gmail.com", url="https://github.com/penguinatnight/hotspot-share",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
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
