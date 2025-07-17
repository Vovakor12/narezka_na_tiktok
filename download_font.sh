#!/bin/bash

# Скрипт для загрузки шрифта Liberation Sans (бесплатная альтернатива Arial)
# Этот шрифт хорошо подходит для субтитров

echo "Загрузка шрифта Liberation Sans..."

# Создаем директорию для шрифтов, если её нет
mkdir -p fonts

# Загружаем шрифт
wget -O fonts/LiberationSans-Bold.ttf "https://github.com/liberationfonts/liberation-fonts/raw/main/src/LiberationSans-Bold.ttf"
wget -O fonts/LiberationSans-Regular.ttf "https://github.com/liberationfonts/liberation-fonts/raw/main/src/LiberationSans-Regular.ttf"

echo "Шрифты загружены в директорию fonts/"
echo "Обновите Dockerfile для копирования шрифтов в контейнер"