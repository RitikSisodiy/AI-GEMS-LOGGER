import os
from setuptools import setup, find_packages
import logger_app


def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''


setup(
    name="logger_app",
    version=logger_app.__version__,
    description=read('DESCRIPTION'),
    long_description=read('README.rst'),
    keywords='logger_app',
    packages=find_packages(),
    author='ritik',
    author_email='ritik.s10120@gmail.com',
    url="gemseducation.com",
    include_package_data=True,
    test_suite='logger_app.tests.runtests.runtests',
    install_requires=[
        "boto3==1.34.40",
        "django-log-outgoing-requests==0.6.1",
        "httpx"
    ]
)
