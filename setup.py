import io

from setuptools import setup

long_description = io.open('README.md', encoding='utf-8').read()

setup(
    name='robothub_oak',
    version='1.0.3',
    description='RobotHub-OAK integration library',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://www.luxonis.com/',
    license='MIT',
    keywords='robothub robot hub connect agent depthai oak sdk',
    author='Luxonis',
    author_email='support@luxonis.com',
    packages=['robothub_oak'],
    package_dir={'': 'src'},  # https://stackoverflow.com/a/67238346/5494277
    include_package_data=True,
    project_urls={
        'Homepage': 'https://github.com/luxonis/robothub-oak/',
        'Documentation': 'https://hub-docs.luxonis.com/',
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Topic :: Software Development',
        'Topic :: Scientific/Engineering',
    ],
)
