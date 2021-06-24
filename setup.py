from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="pyalimony",
    version="2021.0.1",
    description="A simple project for autoposting excuse in Twitter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jtprogru/pyalimony",
    author="Michael (jtprogru) Savin",
    author_email="jtprogru@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "License :: OSI Approved :: WTFPL",
        "Programming Language :: Python :: 3.9",
        "Natural Language :: Russian",
    ],
    keywords="sample, alimony, development, calculate",
    package_dir={"": ""},
    packages=find_packages(where=""),
    python_requires=">=3.9, <4",
    install_requires=[""],
    extras_require={
        "dev": ["autopep8", "flake8", "flake8-colors"],
        "test": ["coverage", "pytest"],
    },
    entry_points={"console_scripts": ["pyalimony=pyalimony:main",],},
    project_urls={
        "Bug Reports": "https://github.com/jtprogru/pyalimony/issues",
        "Patreon": "https://patreon.com/jtprogru",
        "Sobe.ru": "https://sobe.ru/na/jtprogru",
        "Source": "https://github.com/jtprogru/pyalimony",
    },
)
