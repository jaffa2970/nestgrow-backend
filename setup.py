from setuptools import setup
from Cython.Build import cythonize

files_to_compile = [
    "app/licensing.py",
    "app/mqtt_client.py",
    "app/main.py",
    "app/models.py",
    "app/database.py",
]

setup(
    ext_modules=cythonize(
        files_to_compile,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        },
        build_dir="build",
    )
)
