from setuptools import setup, find_packages

setup(
    name="nuc-linux-studio",
    version="2.0.0",
    description="Linux NUC Studio for Fan, Keyboard, and Battery Control",
    packages=find_packages(include=["backend", "backend.*", "ui", "ui.*"]),
    entry_points={
        "console_scripts": [
            "nuc-studio=ui.main:main",
            "nuc-cli=cli:main"
        ]
    },
    install_requires=[],
    author="Adrian Sandru",
)
