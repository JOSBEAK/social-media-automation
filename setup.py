from setuptools import find_packages, setup


setup(
    name="social-media-automation",
    version="0.3.0",
    description="Extensible Instagram and X browser automation runner",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "playwright==1.52.0",
        "fastapi==0.115.6",
        "starlette==0.41.3",
        "uvicorn[standard]==0.34.0",
        "python-multipart==0.0.20",
        "cryptography==44.0.0",
    ],
)
