# fortunaisk/setup.py

from setuptools import setup, find_packages

setup(
    name='aa-fortunaisk',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        # Ajoutez ici vos dépendances, par exemple :
        'Django>=3.2',
        'allianceauth>=4.0',
        'corptools>=4.0',
    ],
    entry_points={
        'console_scripts': [
            # Si vous avez des commandes à exposer
        ],
    },
)
