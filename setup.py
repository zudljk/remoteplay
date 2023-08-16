import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="remoteplay",
    version='0.1',
    author="zudljk",
    author_email="zudljk@email.de",
    description="Run remote games on Paperspace",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
)