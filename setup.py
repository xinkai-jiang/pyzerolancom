from setuptools import setup

setup(
    name="pyzerolancom",
    version="1.0.1",
    install_requires=["zmq", "colorama", "msgpack"],
    include_package_data=True,
    packages=["pyzerolancom"],
)
