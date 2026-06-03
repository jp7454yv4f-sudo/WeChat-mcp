"""Setup script for wechat-mcp."""
from setuptools import setup

setup(
    name="wechat-mcp",
    version="0.1.0",
    description="MCP Server for WeChat — let AI read and send WeChat messages",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Lozzi",
    author_email="jp7454yv4f-sudo@users.noreply.github.com",
    url="https://github.com/jp7454yv4f-sudo/WeChat-mcp",
    license="AGPL-3.0-only",
    packages=["wechat_mcp"],
    python_requires=">=3.10",
    install_requires=[
        "mcp>=1.0.0",
        "opencv-python-headless>=4.8.0",
        "numpy>=1.24.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "wechat-mcp=wechat_mcp.server:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
)
