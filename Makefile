.PHONY: help setup install organize audit dashboard clean push

help:
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║     BELENTANI INFRASTRUCTURE — Comandos Disponibles      ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Setup e instalación:"
	@echo "  make setup           Instalar dependencias y crear directorios"
	@echo "  make install         pip install -r requirements.txt"
	@echo ""
	@echo "Automatización:"
	@echo "  make organize        Organizar archivos (simulación)"
	@echo "  make organize-apply  Organizar y MOVER (CUIDADO)"
	@echo "  make audit           Auditoría completa de GitHub"
	@echo ""
	@echo "Monitoreo:"
	@echo "  make dashboard       Iniciar dashboard web (http://localhost:8765)"
	@echo "  make monitor         Monitoreo en tiempo real"
	@echo ""
	@echo "Desarrollo:"
	@echo "  make clean           Limpiar caché y logs"
	@echo "  make lint            Revisar código"
	@echo ""
	@echo "Git:"
	@echo "  make push            Empujar cambios a GitHub"
	@echo ""

setup:
	python setup.py

install:
	pip install -r requirements.txt

organize:
	python core/organizer.py --include-subdirs

organize-apply:
	@echo "⚠️  CUIDADO: Esto MOVERÁ archivos de verdad"
	@read -p "Confirma? (si/no) " confirm && [ "$$confirm" = "si" ] && python core/organizer.py --apply --include-subdirs

audit:
	python core/github_auditor.py --all

dashboard:
	python web/dashboard.py --host 127.0.0.1 --port 8765

monitor:
	python ops/monitor.py --daemon

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache build dist *.egg-info
	rm -f logs/*.log

lint:
	flake8 core/ ops/ web/ --max-line-length=120
	black --check core/ ops/ web/

push:
	git add -A
	git commit -m "Infrastructure update $(shell date +%Y-%m-%d)"
	git push origin main

.DEFAULT_GOAL := help
