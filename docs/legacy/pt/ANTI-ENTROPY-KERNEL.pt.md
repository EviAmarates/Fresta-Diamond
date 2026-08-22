# Diamond — cláusula anti-entropia executável

Estado: **admissão mínima implementada; execução, cristalização e Φ− ainda
WIP**.

## Leitura constitucional

A cláusula anti-entropia do Volume I não é tratada aqui principalmente como uma
regra jurídica. Ela define a continuidade de identidade do Fresta:

> Uma implementação que remove ou contorna as restrições constitutivas de
> coerência pode continuar a existir como software, mas deixa de ser uma
> implementação admissível do Fresta.

O kernel não tenta impedir que todo código malicioso exista. Impede que esse
código obtenha autoridade operacional dentro do runtime ou se apresente
coerentemente como módulo Fresta.

## Análise de três ordens

- **O1 — manifestação:** pacote, módulo, blueprint, operação ou resultado
  apresentado ao runtime.
- **O2 — relação:** capacidades declaradas, proveniência, dependências, efeitos,
  evidência e comportamento observado.
- **O3 — condição de identidade:** invariantes constitutivas que determinam se
  a manifestação pode receber autoridade enquanto componente Fresta.

Uma declaração como `compatible = true` é apenas uma proposta. A compatibilidade
é derivada pelo kernel e nunca escolhida pelo próprio módulo.

## Princípio fail-closed

```text
compatibilidade não demonstrada
  -> autoridade não concedida
```

O kernel não precisa de provar intenção psicológica maliciosa. Deve bloquear
violações observáveis, capacidades não justificadas e efeitos que escapem ao
contrato.

## Fronteiras de aplicação

### 1. Admissão

- identidade, versão e proveniência verificáveis;
- contrato e capacidades explícitos;
- schemas compatíveis;
- nenhuma tentativa de substituir invariantes constitucionais.

O corte executável atual vive em `anti_entropy.py` e no `ModuleRegistry`:

- a origem é fornecida pelo loader, fora do manifesto candidato;
- módulos comunitários exigem proveniência e digest SHA-256 verificado pelo
  loader;
- capacidades, efeitos e permissões constitucionais proibidos causam rejeição
  mesmo em módulos internos;
- operações comunitárias com efeitos exigem fronteira de permissão e modos de
  falha declarados;
- `verify()` devolve um relatório imutável e só produz `VERIFIED` quando o
  relatório é admissível;
- rejeições impedem `enable()` e produzem eventos `MODULE_REJECTED`.

Isto valida o manifesto observável; ainda não verifica assinaturas nem inspeciona
ou isola bytecode comunitário.

### 2. Planeamento

- dependências completas e acíclicas;
- âmbito e objetivo preservados;
- cadeia coerente com as capacidades registadas;
- nenhum efeito oculto no plano.

### 3. Autorização

- princípio de menor autoridade;
- grants limitados por recurso, operação e duração;
- ausência de permissão equivale a proibição.

### 4. Execução

- efeitos externos passam obrigatoriamente pelo `EffectBroker`;
- comportamento divergente do plano interrompe a execução;
- módulos comunitários hostis exigirão futuramente isolamento por processo ou
  RPC, pois contratos Python in-process não são uma sandbox de segurança.

### 5. Cristalização

- execução técnica bem-sucedida não implica validade epistemológica;
- resultados sem proveniência, evidência ou estatuto adequado não entram na
  memória positiva;
- o módulo não pode declarar a própria conclusão como confirmada.

### 6. Auditoria Φ−

- cada rejeição conserva proposta, âmbito, regra violada e comportamento
  observado;
- tentativas recorrentes podem formar padrões Φ−;
- esses padrões informam preflight, reparação e quarentena futuras;
- a memória Φ− não concede ao módulo rejeitado qualquer autoridade adicional.

## Violações inicialmente bloqueáveis

- remoção ou falsificação de proveniência;
- escrita direta em memória persistente fora do broker;
- promoção de cartões sem validação;
- ocultação ou alteração de remainders;
- capacidades executadas mas não declaradas;
- alteração de um artefacto depois de validado;
- tentativa de substituir validadores ou invariantes do kernel;
- apresentação de fecho técnico como confirmação semântica;
- efeitos de rede, ficheiro ou processo fora do grant autorizado.

## Relação com os componentes atuais

- `Registry`: recebe a candidatura e deriva a admissão mínima; não certifica
  confiança por nome.
- contratos imutáveis: fixam a manifestação declarada.
- `PlanValidator`: verifica a cadeia técnica antes da execução.
- `Controller`: decide se o plano pode receber autoridade.
- `EffectBroker`: medeia e audita efeitos.
- `OntologicalValidator`: verifica o testemunho estrutural.
- `EventJournal`: preserva descoberta, admissão/rejeição, fases, operações e
  efeitos; faltam os eventos próprios de cristalização.
- `JsonlJournalArchive`: já sela e verifica o trilho histórico; faltam política
  de retenção, isolamento multiprocesso e associação formal às decisões de
  confiança dos módulos.
- memória Φ− WIP: compactará exclusões recorrentes em padrões e regras
  contextuais.

## Limite honesto

Nenhum kernel consegue detetar universalmente intenção maliciosa ou verdade
semântica apenas por inspeção estática. A garantia correta é composta:

- código restringe capacidades e efeitos observáveis;
- evidência e proveniência suportam afirmações;
- a LLM pode propor avaliações semânticas;
- validadores conservam autoridade;
- dúvida não resolvida impede promoção e mantém a proposta em quarentena.

## Sequência recomendada

Esta ideia não substitui os cortes já planeados. Encaixa-se neles:

1. contrato de evidência e estatuto epistémico;
2. journal append-only de validação e efeitos;
3. estender a política anti-entropia da admissão já executável para
   autorização e cristalização;
4. memória Φ− e agregação de padrões;
5. isolamento forte de módulos comunitários;
6. primeira fatia vertical do `/learn`;
7. conceitos, tópicos, atenção, sleep e integrações externas por incrementos
   testados.

O primeiro corte deve testar módulos falsos e efeitos simulados. Não deve
carregar código comunitário real, tocar na `data/` de produção ou afirmar
sandboxing que ainda não existe.

## Primeiro preflight de propostas autónomas

O Diamond já reutiliza esta política para avaliar desenhos não executáveis de
módulos. A capability, schemas e camada são ancorados pelo host; efeitos e
permissões só podem usar a fronteira explícita do pedido, vazia por defeito.
Tentativas de alterar controller, Gatekeepers, EffectBroker ou blueprints são
rejeitadas e arquivadas.

Este resultado não admite código: prova apenas que as declarações observáveis
do desenho não violaram o preflight atual. Scaffold, sandbox, assinatura,
descoberta e `enable()` continuam fases futuras e separadas.
