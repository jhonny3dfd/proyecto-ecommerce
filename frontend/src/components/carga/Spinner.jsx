import './Spinner.css';

// Va dentro del botón junto a su texto ("Guardando..."), que es lo que oye el lector de pantalla
export default function Spinner() {
  return <span aria-hidden="true" className="spinner" />;
}
