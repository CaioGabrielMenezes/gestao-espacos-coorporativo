import { expect, test } from '@playwright/test'

/**
 * Fluxo completo contra o backend real.
 *
 * Os testes rodam em sequência sobre o mesmo banco semeado, na ordem em que um
 * coordenador usaria o sistema: olhar o prédio, otimizar, entender a
 * recomendação, intervir, e cadastrar.
 */

const API = 'http://127.0.0.1:8001'

test.describe.configure({ mode: 'serial' })

test('dashboard mostra os indicadores do prédio semeado', async ({ page }) => {
  await page.goto('/dashboard')

  await expect(page.getByRole('heading', { name: 'Ocupação do prédio' })).toBeVisible()

  // As três taxas precisam aparecer separadas: colapsá-las num número só é o
  // erro que o painel existe para evitar.
  await expect(page.getByText('Utilização das salas')).toBeVisible()
  await expect(page.getByText('Aproveitamento')).toBeVisible()

  // 18 salas nos 9 andares vêm do seed.
  await expect(page.getByText('de 18 salas em uso')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ocupação por andar' })).toBeVisible()
})

test('mapa desenha os nove andares com percentual escrito', async ({ page }) => {
  await page.goto('/mapa')

  for (const andar of [1, 5, 9]) {
    await expect(page.getByText(`Andar ${andar}`, { exact: true })).toBeVisible()
  }

  // A informação não pode depender só de cor.
  await expect(page.locator('.sala__percentual').first()).toContainText('%')
  await expect(page.getByText('Subutilizada')).toBeVisible()
})

test('otimização aloca 11 equipes e alerta a que não cabe', async ({ page }) => {
  await page.goto('/recomendacoes')
  await page.getByRole('button', { name: /Gerar alocação otimizada|Nova otimização/ })
    .first()
    .click()

  // A equipe de 92 pessoas não cabe na maior sala, de 80: vira alerta, nunca
  // uma alocação forçada.
  await expect(page.getByText('Operações Delta')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(/comporta 80 pessoas; equipe tem 92/)).toBeVisible()

  // 11 das 12 equipes do seed cabem em alguma sala.
  await expect(page.locator('.lista-recomendacoes > li')).toHaveCount(11)
  await expect(page.getByRole('heading', { name: /Alocações propostas \(11\)/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Equipes sem sala \(1\)/ })).toBeVisible()
})

test('explicabilidade fica a um clique da lista', async ({ page }) => {
  await page.goto('/recomendacoes')

  const primeira = page.locator('.recomendacao__linha').first()
  await expect(page.getByText('Alternativas avaliadas', { exact: true })).toBeHidden()
  await expect(primeira).toHaveAttribute('aria-expanded', 'false')

  await primeira.click()
  await expect(primeira).toHaveAttribute('aria-expanded', 'true')

  await expect(page.getByText('Alternativas avaliadas', { exact: true })).toBeVisible()
  await expect(page.locator('.explicacao__justificativa')).not.toBeEmpty()
})

test('aceitar uma recomendação registra a intervenção', async ({ page }) => {
  await page.goto('/recomendacoes')
  await page.locator('.recomendacao__linha').first().click()
  await page.getByRole('button', { name: 'Aceitar', exact: true }).click()

  await expect(page.locator('.recomendacao--aceita')).toHaveCount(1)

  // A intervenção precisa aparecer no monitoramento: é o rastro de governança.
  await page.goto('/monitoramento')
  await expect(page.getByText(/Intervenções/i).first()).toBeVisible()
})

test('re-otimizar preserva o que foi aceito', async ({ page, request }) => {
  const antes = await (await request.get(`${API}/api/alocacoes/execucoes`)).json()
  const execucaoAnterior = antes[0].execucao_id

  const detalhe = await (
    await request.get(`${API}/api/alocacoes/execucoes/${execucaoAnterior}`)
  ).json()
  const aceita = detalhe.recomendacoes.find((r) => r.status === 'aceita')
  expect(aceita, 'o teste anterior deveria ter deixado uma alocação aceita').toBeTruthy()

  await page.goto('/recomendacoes')
  await page.getByRole('button', { name: 'Re-otimizar mantendo decisões' }).click()
  await page.waitForTimeout(1500)

  const depois = await (await request.get(`${API}/api/alocacoes/execucoes`)).json()
  const nova = await (
    await request.get(`${API}/api/alocacoes/execucoes/${depois[0].execucao_id}`)
  ).json()

  const mesmaEquipe = nova.recomendacoes.find((r) => r.equipe_id === aceita.equipe_id)
  expect(mesmaEquipe.sala_id).toBe(aceita.sala_id)
})

test('sala criada pelo formulário aparece na lista e no mapa', async ({ page }) => {
  await page.goto('/cadastro/salas')
  await page.getByRole('button', { name: 'Nova sala' }).click()

  await page.getByLabel(/Identificação/).fill('Sala 999')
  await page.getByLabel(/Andar/).selectOption('4')
  await page.getByLabel(/Capacidade/).fill('33')
  await page.getByLabel(/Recursos/).fill('projetor, wifi')
  await page.getByRole('button', { name: 'Criar sala' }).click()

  await expect(page.getByRole('rowheader', { name: 'Sala 999' })).toBeVisible()

  // O cadastro tem de refletir no resto do sistema, não só na própria tela.
  await page.goto('/mapa')
  await expect(page.getByText('Sala 999')).toBeVisible()
})

test('capacidade zero é barrada antes de sair do navegador', async ({ page }) => {
  await page.goto('/cadastro/salas')
  await page.getByRole('button', { name: 'Nova sala' }).click()

  await page.getByLabel(/Identificação/).fill('Sala inválida')
  const capacidade = page.getByLabel(/Capacidade/)
  await capacidade.fill('0')
  await page.getByRole('button', { name: 'Criar sala' }).click()

  // A validação nativa do campo impede o envio: o backend também recusaria,
  // mas errar cedo poupa uma ida ao servidor.
  expect(await capacidade.evaluate((el) => el.checkValidity())).toBe(false)
  await expect(page.getByRole('rowheader', { name: 'Sala inválida' })).toHaveCount(0)
})

test('erro do backend chega à tela quando o navegador deixa passar', async ({ page }) => {
  // Identificação duplicada é válida para o HTML e recusada pelo banco: é o
  // caminho que prova que a mensagem do servidor chega ao usuário.
  await page.goto('/cadastro/salas')
  await page.getByRole('button', { name: 'Nova sala' }).click()

  await page.getByLabel(/Identificação/).fill('Sala 101')
  await page.getByLabel(/Capacidade/).fill('10')
  await page.getByRole('button', { name: 'Criar sala' }).click()

  await expect(page.getByRole('alert')).toContainText(/já existe uma sala/i)
})

test('formulário de restrição se adapta ao tipo escolhido', async ({ page }) => {
  await page.goto('/cadastro/restricoes')
  await page.getByRole('button', { name: 'Nova restrição' }).click()

  await page.getByLabel(/^Tipo/).selectOption({ label: 'Andar permitido' })
  await expect(page.getByLabel(/Aplicar a \(equipe\)/)).toBeVisible()
  await expect(page.getByLabel(/Andares permitidos/)).toBeVisible()

  await page.getByLabel(/^Tipo/).selectOption({ label: 'Sala reservada a setor' })
  await expect(page.getByLabel(/Aplicar a \(sala\)/)).toBeVisible()
  await expect(page.getByLabel(/Setor com reserva/)).toBeVisible()
  await expect(page.getByLabel(/Andares permitidos/)).toBeHidden()
})

test('excluir setor avisa que as equipes vão junto', async ({ page }) => {
  await page.goto('/cadastro/setores')

  let mensagem = ''
  page.on('dialog', async (dialogo) => {
    mensagem = dialogo.message()
    await dialogo.dismiss()
  })

  await page.getByRole('button', { name: 'Excluir' }).first().click()
  await expect.poll(() => mensagem).toMatch(/equipes deste setor serão excluídas/i)
})

test('backend fora do ar mostra erro tratado, não tela branca', async ({ page }) => {
  await page.route('**/api/**', (rota) => rota.abort())
  await page.goto('/dashboard')

  await expect(page.getByRole('alert')).toContainText(/backend está rodando/)
})
