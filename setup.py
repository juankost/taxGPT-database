from setuptools import setup, find_packages

# Read requirements.txt and use it for the install_requires option
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="taxgpt-database",
    version="0.1.0",
    packages=find_packages(),
    install_requires=requirements,
    # Additional metadata about your package
)
