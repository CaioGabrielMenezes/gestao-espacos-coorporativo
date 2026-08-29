/**
 * Campos de formulário.
 *
 * Todos são controlados e todos rotulam via <label htmlFor>, não por
 * placeholder: placeholder some quando se digita, e um formulário sem rótulo
 * visível é inutilizável para leitor de tela e ruim para todo mundo.
 */

import { useEffect, useId, useState } from 'react'

function Envolver({ id, rotulo, dica, obrigatorio, children }) {
  return (
    <div className="campo">
      <label htmlFor={id}>
        {rotulo}
        {obrigatorio && <span aria-hidden="true"> *</span>}
      </label>
      {children}
      {dica && <small className="campo__dica">{dica}</small>}
    </div>
  )
}

export function CampoTexto({ rotulo, valor, aoMudar, dica, obrigatorio, ...resto }) {
  const id = useId()
  return (
    <Envolver id={id} rotulo={rotulo} dica={dica} obrigatorio={obrigatorio}>
      <input
        id={id}
        type="text"
        value={valor ?? ''}
        required={obrigatorio}
        onChange={(e) => aoMudar(e.target.value)}
        {...resto}
      />
    </Envolver>
  )
}

export function CampoNumero({ rotulo, valor, aoMudar, dica, obrigatorio, ...resto }) {
  const id = useId()
  return (
    <Envolver id={id} rotulo={rotulo} dica={dica} obrigatorio={obrigatorio}>
      <input
        id={id}
        type="number"
        value={valor ?? ''}
        required={obrigatorio}
        // Campo numérico vazio vira null, não 0: "não informado" e "zero" são
        // coisas diferentes, e o backend rejeita zero em capacidade.
        onChange={(e) => aoMudar(e.target.value === '' ? null : Number(e.target.value))}
        {...resto}
      />
    </Envolver>
  )
}

export function CampoSelect({
  rotulo,
  valor,
  aoMudar,
  opcoes,
  dica,
  obrigatorio,
  vazio = '—',
}) {
  const id = useId()
  return (
    <Envolver id={id} rotulo={rotulo} dica={dica} obrigatorio={obrigatorio}>
      <select
        id={id}
        value={valor ?? ''}
        required={obrigatorio}
        onChange={(e) => {
          const bruto = e.target.value
          if (bruto === '') return aoMudar(null)
          const opcao = opcoes.find((o) => String(o.valor) === bruto)
          aoMudar(opcao ? opcao.valor : bruto)
        }}
      >
        <option value="">{vazio}</option>
        {opcoes.map((o) => (
          <option key={String(o.valor)} value={String(o.valor)}>
            {o.rotulo}
          </option>
        ))}
      </select>
    </Envolver>
  )
}

export function CampoMultiSelect({ rotulo, valores, aoMudar, opcoes, dica }) {
  const id = useId()
  const selecionados = (valores ?? []).map(String)
  return (
    <Envolver
      id={id}
      rotulo={rotulo}
      dica={dica || 'Segure Ctrl (ou Cmd) para escolher mais de um'}
    >
      <select
        id={id}
        multiple
        size={Math.min(opcoes.length || 1, 6)}
        value={selecionados}
        onChange={(e) => {
          const escolhidos = Array.from(e.target.selectedOptions).map((o) => o.value)
          aoMudar(
            escolhidos.map((v) => {
              const opcao = opcoes.find((o) => String(o.valor) === v)
              return opcao ? opcao.valor : v
            })
          )
        }}
      >
        {opcoes.map((o) => (
          <option key={String(o.valor)} value={String(o.valor)}>
            {o.rotulo}
          </option>
        ))}
      </select>
    </Envolver>
  )
}

export function CampoCheckbox({ rotulo, valor, aoMudar, dica }) {
  const id = useId()
  return (
    <div className="campo campo--checkbox">
      <input
        id={id}
        type="checkbox"
        checked={Boolean(valor)}
        onChange={(e) => aoMudar(e.target.checked)}
      />
      <label htmlFor={id}>{rotulo}</label>
      {dica && <small className="campo__dica">{dica}</small>}
    </div>
  )
}

const separar = (texto) =>
  texto
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

/**
 * Lista de textos livres, digitada separada por vírgula.
 *
 * O texto digitado vive em estado local, e não no array do formulário. Se o
 * input fosse alimentado por `valores.join(', ')`, digitar a vírgula de
 * "projetor," seria desfeito na renderização seguinte — o array ainda não tem
 * o segundo item, então o join devolve "projetor" e a vírgula some sob o
 * cursor. O array só é reimposto quando muda por fora (ao editar outro
 * registro).
 */
export function CampoListaTexto({ rotulo, valores, aoMudar, dica }) {
  const id = useId()
  const [texto, setTexto] = useState(() => (valores ?? []).join(', '))

  useEffect(() => {
    const deFora = (valores ?? []).join(', ')
    if (separar(texto).join(', ') !== deFora) setTexto(deFora)
    // Sincroniza só quando o valor externo diverge do que o texto representa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valores])

  return (
    <Envolver
      id={id}
      rotulo={rotulo}
      dica={dica || 'Separe por vírgula. Ex: projetor, wifi'}
    >
      <input
        id={id}
        type="text"
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value)
          aoMudar(separar(e.target.value))
        }}
      />
    </Envolver>
  )
}
