#!/bin/bash
# Script de subida rápida para Sync Master

echo "Preparando cambios..."
git add .

echo "¿Qué hiciste en este cambio? (Escribe el mensaje del commit):"
read mensaje

if [ -z "$mensaje" ]; then
    mensaje="Actualización menor"
fi

git commit -m "$mensaje"

echo "Subiendo a GitHub..."
git push

echo "¡Proyecto sincronizado!"