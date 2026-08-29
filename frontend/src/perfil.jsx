/**
 * Perfil de acesso — os dois níveis de decisão da seção 2 do enunciado.
 *
 * O Coordenador Geral administra o prédio: cadastra salas, executa a
 * otimização global e decide sobre as recomendações. Os Coordenadores de Setor
 * informam os dados das próprias equipes e suas restrições.
 *
 * IMPORTANTE — isto é separação ORGANIZACIONAL, não de segurança. Não há
 * autenticação (fora do escopo do enunciado), então nada impede alguém de
 * chamar a API diretamente. O que o perfil faz é dois: mostrar a cada papel
 * apenas o que lhe compete, e registrar na governança quem executou cada ação.
 * Tratar isto como controle de acesso seria enganoso.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api'

const CHAVE = 'perfil-atual'
const GERAL = { tipo: 'geral', setorId: null, nome: 'Coordenador Geral' }

const PerfilContexto = createContext(null)

function ler() {
  try {
    const bruto = localStorage.getItem(CHAVE)
    return bruto ? JSON.parse(bruto) : GERAL
  } catch {
    // Navegador com armazenamento bloqueado não deve impedir o uso do sistema.
    return GERAL
  }
}

export function ProvedorPerfil({ children }) {
  const [perfil, setPerfilEstado] = useState(ler)
  const [setores, setSetores] = useState([])

  useEffect(() => {
    api
      .setores()
      .then(setSetores)
      // Falha ao listar setores não pode derrubar a aplicação: sem a lista, o
      // seletor mostra apenas o Coordenador Geral.
      .catch(() => setSetores([]))
  }, [])

  const setPerfil = useCallback((novo) => {
    setPerfilEstado(novo)
    try {
      localStorage.setItem(CHAVE, JSON.stringify(novo))
    } catch {
      // Sem persistência o perfil vale só para esta sessão — aceitável.
    }
  }, [])

  const valor = useMemo(
    () => ({
      perfil,
      setPerfil,
      setores,
      geral: GERAL,
      ehGeral: perfil.tipo === 'geral',
      // Identificação registrada na governança de cada ação.
      usuario:
        perfil.tipo === 'geral' ? 'coordenador-geral' : `coordenador-setor:${perfil.nome}`,
    }),
    [perfil, setPerfil, setores]
  )

  return <PerfilContexto.Provider value={valor}>{children}</PerfilContexto.Provider>
}

export function usarPerfil() {
  const contexto = useContext(PerfilContexto)
  if (!contexto) {
    throw new Error('usarPerfil precisa estar dentro de <ProvedorPerfil>')
  }
  return contexto
}

export function SeletorPerfil() {
  const { perfil, setPerfil, setores, geral } = usarPerfil()

  return (
    <label className="seletor-perfil">
      <span>Atuando como</span>
      <select
        value={perfil.tipo === 'geral' ? 'geral' : String(perfil.setorId)}
        onChange={(e) => {
          if (e.target.value === 'geral') return setPerfil(geral)
          const setor = setores.find((s) => String(s.id) === e.target.value)
          if (setor) {
            setPerfil({ tipo: 'setor', setorId: setor.id, nome: setor.nome })
          }
        }}
      >
        <option value="geral">Coordenador Geral</option>
        {setores.map((s) => (
          <option key={s.id} value={String(s.id)}>
            Coordenador · {s.nome}
          </option>
        ))}
      </select>
    </label>
  )
}
