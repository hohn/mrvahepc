from pathlib import Path
import tomllib
from setuptools import setup, find_packages


def load_dependencies() -> list[str]:
    """Read the dependency list directly from pyproject.toml for consistency."""
    pyproject_path = Path(__file__).with_name("pyproject.toml")
    if not pyproject_path.exists():
        return []
    data = tomllib.loads(pyproject_path.read_text())
    return data.get("project", {}).get("dependencies", [])


setup(
    name="mrvahepc",
    version="0.1.0",
    description="A Python package for serving CodeQL databases",
    author="Michael Hohn",
    author_email="hohn@github.com",
    packages=find_packages(),
    install_requires=load_dependencies(),
    scripts=["bin/host-hepc-init", "bin/host-hepc-serve",
             "bin/mc-hepc-init", "bin/mc-hepc-serve"],
)
