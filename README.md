# FortunaISK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Avertissement** : Ce projet est en **développement actif** et **n'est pas prêt** pour une utilisation en production.

FortunaISK est un module de loterie mensuelle pour [Alliance Auth](https://gitlab.com/allianceauth/allianceauth). Son objectif est de simplifier l'achat de billets, d'automatiser la vérification des paiements et de fournir une interface conviviale pour suivre les gagnants et l'historique des loteries. Cependant, comme FortunaISK est encore en cours de développement, certaines fonctionnalités restent incomplètes ou sont susceptibles de changer.

## Table des Matières

- [Fonctionnalités (En Développement)](#fonctionnalit%C3%A9s-en-d%C3%A9veloppement)
- [Installation](#installation)
- [Configuration](#configuration)
- [Exécution de l'Application](#ex%C3%A9cution-de-lapplication)
- [Configuration de Celery et des Tâches Périodiques](#configuration-de-celery-et-des-t%C3%A2ches-p%C3%A9riodiques)
- [Utilisation](#utilisation)
- [Plans Futurs](#plans-futurs)
- [Licence](#licence)

## Fonctionnalités (En Développement)

- **Prix des Billets & Référence Configurables**\
  Définissez un prix de billet en ISK personnalisé et assignez des références de loterie uniques.

- **Vérification Automatisée des Paiements**\
  Intègre `allianceauth-corp-tools` (en cours) pour surveiller les transactions de portefeuille et valider les achats de billets.

- **Historique des Gagnants**\
  Composant UI à venir pour afficher les gagnants passés, leurs montants de prix et d'autres détails pertinents.

## Installation

### **Prérequis**

- **Système d'Exploitation :** Basé sur Linux (testé sur Ubuntu 20.04+)
- **Python :** 3.8 ou supérieur
- **Django :** Compatible avec la version utilisée par votre installation Alliance Auth
- **Base de Données :** PostgreSQL (recommandé) ou autres bases de données supportées
- **Celery :** Pour le traitement asynchrone des tâches
- **Redis ou RabbitMQ :** Comme courtier de messages pour Celery
- **Alliance Auth :** Déjà installé et configuré
