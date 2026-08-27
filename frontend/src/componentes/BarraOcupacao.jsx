/**
 * Barra de ocupação em CSS puro — sem biblioteca de gráficos.
 *
 * A faixa de cor não é decoração: ocupação muito baixa é desperdício e
 * ocupação muito alta é aperto. Ambos precisam saltar aos olhos.
 */
function faixa(percentual) {
  if (percentual === 0) return 'vazia'
  if (percentual < 40) return 'baixa'
  if (percentual > 95) return 'cheia'
  return 'boa'
}

export default function BarraOcupacao({ percentual, rotulo, detalhe }) {
  const largura = Math.min(percentual, 100)

  return (
    <div className="barra">
      <div className="barra__cabecalho">
        <span className="barra__rotulo">{rotulo}</span>
        <span className="barra__valor">{percentual}%</span>
      </div>
      <div
        className="barra__trilho"
        role="meter"
        aria-valuenow={percentual}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Ocupação: ${rotulo}`}
      >
        <div
          className={`barra__preenchimento barra__preenchimento--${faixa(percentual)}`}
          style={{ width: `${largura}%` }}
        />
      </div>
      {detalhe && <span className="barra__detalhe">{detalhe}</span>}
    </div>
  )
}
