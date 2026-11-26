import { useEffect, useRef } from 'react';

// El diálogo nativo contiene el foco y vuelve inerte el fondo, sin ARIA que duplique su semántica.
export default function Dialogo({ tituloId, className, onCerrar, cerrarFuera = false, children }) {
  const referencia = useRef(null);
  useEffect(() => {
    const anterior = document.activeElement;
    const dialogo = referencia.current;
    dialogo.showModal();
    dialogo.querySelector('[data-foco-inicial]')?.focus();
    return () => {
      dialogo.close();
      if (anterior?.isConnected) anterior.focus({ preventScroll: true });
    };
  }, []);

  return (
    <dialog ref={referencia} className={className} aria-labelledby={tituloId}
      onCancel={evento => { evento.preventDefault(); onCerrar(); }}
      onKeyDown={evento => {
        if (evento.key !== 'Tab') return;
        const controles = [...evento.currentTarget.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')]
          .filter(control => control.getClientRects().length > 0);
        const primero = controles[0];
        const ultimo = controles.at(-1);
        // Chromium permite llegar a la barra del navegador desde los extremos del diálogo.
        // Mantener el recorrido dentro del aviso también al invertirlo desde el título.
        if (evento.shiftKey && (document.activeElement === primero || document.activeElement.hasAttribute('data-foco-inicial'))) {
          evento.preventDefault(); ultimo?.focus();
        } else if (!evento.shiftKey && document.activeElement === ultimo) {
          evento.preventDefault(); primero?.focus();
        }
      }}
      onClick={evento => {
        if (!cerrarFuera || evento.target !== evento.currentTarget) return;
        const caja = evento.currentTarget.getBoundingClientRect();
        if (evento.clientX < caja.left || evento.clientX > caja.right || evento.clientY < caja.top || evento.clientY > caja.bottom) onCerrar();
      }}>
      {children}
    </dialog>
  );
}
