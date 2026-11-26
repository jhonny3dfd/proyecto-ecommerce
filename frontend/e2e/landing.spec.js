import { test, expect } from '@playwright/test';

// Página inicial y navegación al catálogo, con API aislada.
const configuracionQA = {
  texto_bienvenida: 'Bienvenido a Ecode QA',
  texto_boton_ingreso: 'Ver catálogo',
  tema_seleccionado: 1,
  paleta_id: 1,
  banner_url: '',
};

const peticionesInesperadas = new WeakMap();

test.beforeEach(async ({ page }) => {
  const inesperadas = [];
  peticionesInesperadas.set(page, inesperadas);
  // Ninguna petición API puede llegar a un backend real, aunque falte un mock.
  await page.route('**/api/**', async (route) => {
    inesperadas.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    await route.abort('blockedbyclient');
  });
  await page.route('**/api/ventas/paginas-legales/', async (route) => {
    await route.fulfill({ json: [] });
  });
  // Simular la configuración pública del backend
  await page.route('**/api/configuracion/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(configuracionQA),
    });
  });

  // Vitrina de la landing vacía: las secciones de productos no se muestran
  await page.route('**/api/catalogo/vitrina/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ mas_vendidos: [], recientes: [] }),
    });
  });

  // Simular un catálogo vacío con paginación, sin modificar la base de datos (SCRUM-179)
  await page.route('**/api/catalogo/productos/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 0, total_pages: 1, current_page: 1, results: [] }),
    });
  });

  await page.route('**/api/catalogo/filtros/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ categorias: [], atributos: {} }),
    });
  });

  // Los mocks anteriores solo aceptan lecturas; una escritura se bloquea y falla.
  await page.route('**/api/**', async (route) => {
    if (route.request().method() !== 'GET') {
      inesperadas.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
      await route.abort('blockedbyclient');
      return;
    }
    await route.fallback();
  });
});

test.afterEach(async ({ page }) => {
  expect(peticionesInesperadas.get(page), 'Todas las llamadas API deben estar simuladas y ser GET').toEqual([]);
});

test('la página inicial muestra la bienvenida y el botón de catálogo', async ({
  page,
}) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Bienvenido a Ecode QA' }),
  ).toBeVisible();

  // Es un enlace: lleva a otra página
  await expect(
    page.getByRole('link', { name: 'Ver catálogo' }),
  ).toBeVisible();
});

test('el botón de bienvenida navega al catálogo', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('link', { name: 'Ver catálogo' }).click();

  await expect(page).toHaveURL(/\/catalogo$/);

  await expect(
    page.getByRole('heading', { name: /catálogo/i }),
  ).toBeVisible();

  await expect(
    page.getByText('No hay productos para mostrar'),
  ).toBeVisible();
});
