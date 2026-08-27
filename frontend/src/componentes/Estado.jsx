/**
 * Estados de carregamento, erro e vazio.
 *
 * Centralizados aqui porque toda tela precisa dos três, e uma tela branca
 * quando o backend cai é o pior desfecho possível numa demonstração.
 */

export function Carregando({ children = 'Carregando…' }) {
  return <p className="estado estado--carregando">{children}</p>
}

export function Erro({ mensagem, aoTentarNovamente }) {
  return (
    <div className="estado estado--erro" role="alert">
      <strong>Não deu certo.</strong>
      <p>{mensagem}</p>
      {aoTentarNovamente && (
        <button type="button" onClick={aoTentarNovamente}>
          Tentar novamente
        </button>
      )}
    </div>
  )
}

export function Vazio({ children }) {
  return <p className="estado estado--vazio">{children}</p>
}
