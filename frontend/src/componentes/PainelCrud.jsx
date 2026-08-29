/**
 * Casca comum das quatro telas de cadastro.
 *
 * As quatro repetem o mesmo ciclo — carregar, listar, abrir formulário, salvar,
 * excluir, recarregar — e só diferem nos campos e nas chamadas de API. Manter
 * esse ciclo em um lugar só evita que uma tela trate erro de um jeito e as
 * outras de outro.
 */

import { useCallback, useEffect, useState } from 'react'
import { Carregando, Erro, Vazio } from './Estado'

/** Carrega uma lista da API e expõe recarga e estados de tela. */
export function useRecurso(carregador) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const recarregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      setDados(await carregador())
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }, [carregador])

  useEffect(() => {
    recarregar()
  }, [recarregar])

  return { dados, erro, carregando, recarregar, setErro }
}

export function PainelCrud({
  titulo,
  descricao,
  itens,
  carregando,
  erro,
  aoRecarregar,
  rotuloNovo,
  formularioAberto,
  aoAbrirNovo,
  aoFechar,
  formulario,
  vazio,
  children,
}) {
  if (carregando && itens == null) return <Carregando />
  if (erro && itens == null) return <Erro mensagem={erro} aoTentarNovamente={aoRecarregar} />

  return (
    <section className="cadastro">
      <header className="cabecalho-secao">
        <div>
          <h3>{titulo}</h3>
          {descricao && <p className="subtitulo">{descricao}</p>}
        </div>
        {!formularioAberto && (
          <button type="button" className="primario" onClick={aoAbrirNovo}>
            {rotuloNovo}
          </button>
        )}
      </header>

      {/* Erro de gravação aparece sem apagar a lista: o usuário precisa ver o
          que digitou junto da mensagem para poder corrigir. */}
      {erro && itens != null && <Erro mensagem={erro} />}

      {formularioAberto && (
        <div className="formulario-painel">
          {formulario}
          <div className="formulario-acoes">
            <button type="button" onClick={aoFechar}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {itens && itens.length === 0 ? <Vazio>{vazio}</Vazio> : children}
    </section>
  )
}

/**
 * Botões de editar e excluir de uma linha.
 *
 * A confirmação recebe a consequência por extenso, e não um "tem certeza?".
 * Apagar um setor apaga junto todas as suas equipes, e quem clica precisa
 * saber disso antes, não depois.
 */
export function AcoesLinha({ aoEditar, aoExcluir, confirmacao }) {
  return (
    <div className="acoes-linha">
      {/* Sem `aoEditar` o botão não aparece: oferecer uma ação que só explica
          por que não existe é pior do que não oferecê-la. */}
      {aoEditar && (
        <button type="button" onClick={aoEditar}>
          Editar
        </button>
      )}
      <button
        type="button"
        className="perigo"
        onClick={() => {
          if (window.confirm(confirmacao)) aoExcluir()
        }}
      >
        Excluir
      </button>
    </div>
  )
}
