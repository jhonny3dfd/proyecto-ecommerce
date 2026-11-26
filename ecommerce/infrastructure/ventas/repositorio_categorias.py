"""Adaptador PostgreSQL de lo que nombra a una categoría del catálogo: el orden de categorías de la tienda y las
categorías elegibles de los planes de suscripción (RF-03.2)."""

from ecommerce.application.categorias import ReferenciasCategorias

from .models import ConfiguracionGlobal, PlanSuscripcion


class DjangoReferenciasCategorias(ReferenciasCategorias):
    def orden(self) -> list[str]:
        return list(ConfiguracionGlobal.objects.filter(pk=1).values_list('orden_categorias', flat=True).first() or [])

    def guardar_orden(self, orden: list[str]) -> None:
        ConfiguracionGlobal.objects.filter(pk=1).update(orden_categorias=orden)

    def categorias_de_planes(self) -> dict[int, list[str]]:
        return {plan_id: list(categorias or [])
                for plan_id, categorias in PlanSuscripcion.objects.values_list('id', 'categorias')}

    def guardar_categorias_de_plan(self, plan_id: int, categorias: list[str]) -> None:
        PlanSuscripcion.objects.filter(pk=plan_id).update(categorias=categorias)
