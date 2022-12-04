import io

from setuptools import setup

setup(
    name='robothub_depthai',
    version='0.0.1',
    description='',
    long_description='',
    long_description_content_type='text/markdown',
    url='https://www.luxonis.com/',
    keywords='robothub robot hub connect agent depthai',
    author='Luxonis',
    author_email='support@luxonis.com',
    packages=['robothub_depthai'],
    package_dir={"": "src"},  # https://stackoverflow.com/a/67238346/5494277
    include_package_data=True,
    project_urls={
        "Documentation": "https://docs.luxonis.com/",
    },
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
