import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { comprobarVista, prepararTienda } from './soporte/tienda';

const NUEVA = 'Otra-Clave-Segura-2026';
const AVISO_ENLACE = 'Si el correo tiene una cuenta en la tienda, te enviamos un enlace para elegir una nueva contraseña.';

async function sinViolaciones(page) {
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
}

// Después de prepararTienda: la última ruta registrada es la que responde
async function simular(page, ruta, respuesta) {
  const cuerpos = [];
  await page.route(`**/api/usuarios/contrasena/${ruta}/`, async route => {
    cuerpos.push(route.request().postDataJSON());
    await route.fulfill({ json: respuesta });
  });
  return cuerpos;
}

test('desde el login se pide el enlace por correo', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page);
  const cuerpos = await simular(page, 'olvido', { detail: AVISO_ENLACE });

  await page.goto('/login');
  await page.getByRole('link', { name: '¿Olvidaste tu contraseña?' }).click();
  await expect(page).toHaveURL(/\/recuperar-contrasena$/);
  await expect(page).toHaveTitle(/^Recuperar contraseña/);
  await sinViolaciones(page);

  await page.getByLabel('Correo electrónico').fill('ana@example.test');
  await page.getByRole('button', { name: 'Enviar enlace' }).press('Enter');
  await expect(page.getByRole('status')).toHaveText(AVISO_ENLACE);
  expect(cuerpos).toEqual([{ email: 'ana@example.test' }]);
  await comprobarVista(page);
  expect(inesperadas).toEqual([]);
});

test('el enlace del correo sale de la URL al abrirlo y deja elegir la nueva contraseña', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page);
  const cuerpos = await simular(page, 'restablecer', { detail: 'Tu contraseña se cambió. Ya puedes iniciar sesión.' });

  await page.goto('/restablecer-contrasena?uid=MQ&token=abc-123');
  // Ni la barra de direcciones ni la analítica ven el token
  expect(await page.evaluate(() => location.pathname + location.search + location.hash)).toBe('/restablecer-contrasena');
  await expect(page.getByRole('heading', { name: 'Nueva contraseña' })).toBeVisible();
  await sinViolaciones(page);

  await page.getByLabel('Nueva contraseña', { exact: true }).fill(NUEVA);
  await page.getByLabel('Repite la nueva contraseña').fill(NUEVA);
  await page.getByRole('button', { name: 'Guardar contraseña' }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('status')).toHaveText('Tu contraseña se cambió. Ya puedes iniciar sesión.');
  expect(cuerpos).toEqual([{ uid: 'MQ', token: 'abc-123', password: NUEVA, password2: NUEVA }]);
  expect(inesperadas).toEqual([]);
});

test('con la sesión iniciada se cambia la contraseña desde el menú de la cuenta', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  const cuerpos = await simular(page, 'cambiar', { detail: 'Tu contraseña se cambió.' });

  await page.goto('/catalogo');
  await page.getByRole('button', { name: /Hola/ }).click();
  await page.getByRole('link', { name: 'Cambiar contraseña' }).click();
  await expect(page.getByRole('heading', { name: 'Cambiar contraseña' })).toBeVisible();
  await sinViolaciones(page);

  await page.getByLabel('Contraseña actual').fill('Clave-Antigua-2025');
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(NUEVA);
  await page.getByLabel('Repite la nueva contraseña').fill(NUEVA);
  await page.getByRole('button', { name: 'Guardar contraseña' }).click();

  await expect(page.getByRole('status')).toHaveText('Tu contraseña se cambió.');
  expect(cuerpos).toEqual([{ actual: 'Clave-Antigua-2025', password: NUEVA, password2: NUEVA }]);
  await comprobarVista(page);
  expect(inesperadas).toEqual([]);
});
