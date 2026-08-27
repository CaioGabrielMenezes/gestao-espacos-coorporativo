/** Indicador numérico com rótulo e, opcionalmente, uma nota explicativa. */
export default function Card({ rotulo, valor, unidade = '', nota, destaque }) {
  return (
    <div className={`card ${destaque ? 'card--destaque' : ''}`}>
      <span className="card__rotulo">{rotulo}</span>
      <span className="card__valor">
        {valor}
        {unidade && <small className="card__unidade">{unidade}</small>}
      </span>
      {nota && <span className="card__nota">{nota}</span>}
    </div>
  )
}
