import os
import sys

import Cython
import setuptools
from Cython.Build import cythonize

with open("requirements.txt") as f:
    required = f.read().splitlines()


def find_pyx(path="."):
    pyx_files = []
    for root, dirs, filenames in os.walk(path):
        for fname in filenames:
            if fname.endswith(".pyx"):
                pyx_files.append(os.path.join(root, fname))
    return pyx_files


extensions = find_pyx()

setup = dict(
    name="hardware_communicator",
    version="0.1",
    author="Julian Kimmig",
    author_email="julian-kimmig@gmx.net",
    description="HardwareCommunicator",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/JulianKimmig/HardwareCommunicator",
    packages=setuptools.find_packages(),
    install_requires=required,
    ext_modules=cythonize(extensions, language_level=3),
    cmdclass={"build_ext": Cython.Build.build_ext},
    package_dir={"hardware_communicator": "hardware_communicator"},
)


def pip_install():
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "."])


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("build_ext")
        sys.argv.append("--inplace")
        pip_install()
    else:
        setuptools.setup(**setup)
