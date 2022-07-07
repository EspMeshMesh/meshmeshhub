# python setup.py sdist --format=zip

from setuptools import find_packages, setup
from meshmesh.hub2 import __version__, __license__, __author__


setup(
    name="meshmesh",
    version = __version__,
    description = "MeshMesh Hub for python",
    package_data = {'': ["LICENSE", "requirements.txt"]},
    author = __author__,
    author_email = 'stefano.pagnottelli@gmail.com',
    platforms = ["any"],
    license = __license__,
    url = "https://github.com/EspMeshMesh/meshmeshhub.git",
    packages = ['meshmesh.gui2', 'meshmesh.hub2'],
    entry_points = {'console_scripts': [
        'meshmeshhub = meshmesh.hub2.__main__:main',
        'meshmeshtest =  meshmesh.hub2.test:main'
    ]},
    namespace_packages = ['meshmesh'],
    install_requires = ['pyserial', 'pyserial-asyncio', 'aiohttp-xmlrpc'],
    )
