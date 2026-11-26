"""Adaptador MongoDB de las categorías del catálogo (RF-03.2): listarlas con sus productos y renombrarlas."""

from ecommerce.application.categorias import CategoriaCatalogo, CategoriasCatalogo

from .documents import Producto


class MongoCategoriasCatalogo(CategoriasCatalogo):
    def listar(self) -> list[CategoriaCatalogo]:
        # Las de los productos activos (publicados o en borrador), como el formulario de producto y el inventario
        filas = Producto._get_collection().aggregate([
            {'$match': {'activo': {'$ne': False}, 'categoria': {'$type': 'string', '$ne': ''}}},
            {'$group': {'_id': '$categoria', 'productos': {'$sum': 1},
                        'publicados': {'$sum': {'$cond': [{'$eq': ['$publicado', False]}, 0, 1]}}}},
        ])
        categorias = [CategoriaCatalogo(fila['_id'], fila['productos'], fila['publicados']) for fila in filas]
        return sorted(categorias, key=lambda c: (c.nombre.casefold(), c.nombre))

    def renombrar(self, desde: str, hacia: str) -> int:
        # Todos los productos con esa categoría, también los inactivos, para que no reaparezca después.
        # Un solo update_many: cada producto cambia de forma atómica
        return Producto._get_collection().update_many(
            {'categoria': desde}, {'$set': {'categoria': hacia}}).modified_count
