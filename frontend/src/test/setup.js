import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// JSDOM no implementa el diálogo modal. Su comportamiento de foco y teclado
// se comprueba con el navegador real; aquí solo se representa su apertura.
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
}
if (!HTMLDialogElement.prototype.close) {
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
}
// JSDOM no implementa la reproducción real de videos.
// Simulamos estos métodos para las pruebas de componentes.
Object.defineProperty(HTMLMediaElement.prototype, 'play', {
  configurable: true,
  writable: true,
  value: vi.fn().mockResolvedValue(undefined),
});

Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
  configurable: true,
  writable: true,
  value: vi.fn(),
});
