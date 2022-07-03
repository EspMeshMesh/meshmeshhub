# python setup.py sdist --format=zip

from setuptools import find_packages, setup
from meshmesh.hub2 import __version__, __license__, __author__


setup(
    name="meshmesh-hub",
    version = __version__,
    description = "Mesh Mesh Hub for python",
    package_data = {'': ["LICENSE", "requirements.txt"]},
    author = __author__,
    author_email = 'stefano.pagnottelli@siralab.com',
    platforms = ["any"],
    license = __license__,
    url = "http://git.siralab.com/meshmesh/meshmesh",
    packages = ['meshmesh.gui2', 'meshmesh.hub2'],
    entry_points = {'console_scripts': ['meshmeshhub = meshmesh.hub2.__main__:main']},
    namespace_packages = ['meshmesh'],
    install_requires = ['pyserial', 'pyserial-asyncio', 'aiohttp-xmlrpc'],
    )
