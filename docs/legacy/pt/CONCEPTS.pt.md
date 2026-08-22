# Conceitos nativos do Diamond

## Papel

Um conceito é uma estrutura versionada que organiza cristais comprometidos por
uma assinatura intensional comum. Não é uma pasta, um simples nome partilhado
nem uma ordem ontológica permanente.

O primeiro corte implementado é deliberadamente estreito:

```text
LearningCommit
  -> retrieval explícito de cristais
  -> proposta com pelo menos dois membros
  -> ConceptRecord / CANDIDATE
  -> histórico versionado
```

A proposta não valida a si própria. O método público do store continua a
recusar conceitos `VALIDATED` ou `CRYSTALLIZED`. Uma promoção validada só pode
atravessar o `ConceptValidationService`, depois de o validador determinístico
produzir e arquivar o relatório correspondente.

## Interface partilhada

O serviço central expõe cinco entradas sobre os mesmos métodos da aplicação:

```text
/concept list
/concept inspect CONCEPT_ID
/concept nominate --scope SCOPE OBJECTIVE
/concept evaluate CONCEPT_ID
/concept resolve [--queries N] [--results N] CONCEPT_ID
```

As duas primeiras são exclusivamente de leitura. `nominate` pode chamar a LLM,
mas o resultado permanece `UNVALIDATED_CONCEPT_NOMINATION` e, quando aceite,
cria apenas um `CANDIDATE`. `evaluate` pede evidência limitada à LLM e entrega-a
ao validador determinístico; a interface não escolhe o estado final. `resolve`
avalia primeiro e só ativa pesquisa dirigida quando o relatório atual expõe
uma parte exata sem selo positivo. Fontes resultantes regressam pelo `/learn`;
apenas cristais ACTIVE podem rever o candidato antes de nova avaliação.

Integrações internas usam `invoke("concept.*", ...)`, sem construir slash
commands. Isso mantém utilizador e futuras blueprints na mesma fronteira sem
dar à LLM acesso direto ao store.

## Contratos

- `ConceptSignature` descreve características, relações, funções, restrições,
  exclusões, exemplos e contraexemplos. Pelo menos um campo intensional é
  obrigatório.
- `ConceptMembership` liga um conceito a um cristal por identidade estável e
  possui o seu próprio estado.
- `ConceptParentLink` representa especialização/âmbito. Pode haver vários pais
  e o store rejeita ciclos.
- `ConceptRecord` possui ID estável, nome canónico, aliases, versão, âmbito,
  membros, pais e referências de validação.

Nenhum destes contratos contém O1, O2 ou O3 intrínsecos. Esses papéis só podem
ser derivados relativamente a um objetivo de análise.

## Catálogos heurísticos externos

Uma tabela, extração do NotebookLM ou pack comunitário pode sugerir conceitos,
mas não equivale a memória aprendida nem a um `ConceptRecord`. O contrato
`UNVALIDATED_CONCEPT_CATALOG` proíbe ordens intrínsecas, selos, referências de
validação e autoridade de promoção.

O intake cria uma folha `STAGED` por entrada: o nome é um elemento `CONCEPT` e
as definições, relações e consequências propostas entram como `HYPOTHESIS`.
Estas heurísticas podem ser revistas, decompostas ou rejeitadas pela LLM, mas
qualquer adoção exige a pipeline normal `/learn -> cristais -> evidência ->
validação conceptual versionada`. A versão anterior nunca é reescrita.

## Estados reservados

Os ciclos de vida já estão tipados para evitar futuras migrações destrutivas:

- conceito: `CANDIDATE`, `VALIDATED`, `CRYSTALLIZED`, `CONTESTED`, `ARCHIVED`;
- pertença: `CANDIDATE`, `SUPPORTED`, `CRYSTALLIZED`, `CONTESTED`, `EXCLUDED`;
- ligação parental: `CANDIDATE`, `SUPPORTED`, `REJECTED`.

O builder produz exclusivamente `CANDIDATE`. A primeira validação interna já
pode produzir `VALIDATED` ou `CONTESTED`; `CRYSTALLIZED` permanece reservado
para repetição independente futura.

## Retrieval e segurança

O builder só usa cristais que a memória autónoma torna recuperáveis sob uma
política explícita:

- `ACTIVE` por defeito;
- `FALLBACK` para admitir deliberadamente cristais `DEFERRED`;
- exclusões de auditoria nunca entram numa proposta positiva.

IDs de conceitos são convertidos em nomes de ficheiro por hash, o histórico é
append-only por versão e alterações de nome preservam aliases. Um nome melhor
não altera a identidade do conceito.

## Selo de derivação

A proveniência de um conceito não deve existir apenas ao nível do registo
inteiro. Cada parte justificável precisa de conservar a sua própria linhagem:

```text
alvo no conceito
  -> contribuição direta | síntese | corroboração | contraevidência
  -> cristais, documentos, fontes externas ou folhas usados
  -> análise que efetuou a transformação
  -> versão do conceito que incorporou o resultado
```

Exemplos de alvos são uma característica da assinatura, uma relação, uma
exclusão, uma pertença ou uma ligação parental. Uma conclusão que combine web e
cartões é uma síntese com várias entradas, não uma nova fonte opaca chamada
“web+cartões”.

`DerivationSeal` contém referências estáveis e verificáveis: alvo, tipo de
contribuição, IDs e tipos das fontes, ID da análise, âmbito, timestamp e digest.
O conteúdo completo permanece nos stores de origem e no journal. Alterar
silenciosamente qualquer parte invalida o digest.

Percentagens por origem podem ser calculadas para apresentação e auditoria, mas
não equivalem a confiança nem concedem promoção. O selo responde “de onde veio
e como foi incorporado”; o relatório de validação responde “o que esta
proveniência permite afirmar”.

## Validação interna

`ConceptValidator` recebe os grafos estrutural e epistémico completos, nunca um
booleano global da LLM. Reutiliza `OntologicalValidator` e
`EpistemicValidator`, exigindo:

- o mesmo objeto, análise e âmbito nos dois grafos e nos selos;
- proveniência já presente nos cristais committed;
- cristais ativos para sustentar pertenças;
- selo positivo para cada pertença e cada elemento estrutural da assinatura;
- ausência de contraevidência viva;
- fecho estrutural e ónus epistémico satisfeitos.

O relatório separa `local_fit`, `structural_state`, `definition_state` e
`recognition_state`. Uma validação puramente interna deixa reconhecimento
externo como `NOT_EVALUATED`.

Resultados possíveis:

- evidência completa: nova versão `VALIDATED`, pertenças `SUPPORTED`;
- lacuna finita: permanece `CANDIDATE`, com relatório e remainders arquivados;
- contraevidência: nova versão `CONTESTED`;
- nenhum destes resultados cristaliza o conceito.

Fontes web só são admissíveis internamente depois de entrarem por `/learn` e
serem preservadas na proveniência de um cristal committed. Uma URL solta num
selo é rejeitada.

## Limitações atuais

- Conceitos ainda não participam no retrieval para uma análise.
- O store é experimental, single-process e sem índice.
- A persistência de conceitos é versionada e usa rename atómico, mas ainda não
  possui recuperação de pendentes equivalente a `LearningCommit`.
- A atualização do eixo de reconhecimento a partir de fontes aprendidas
  continua WIP.
- A pesquisa externa já produz source units no workspace, mas o ciclo
  `/learn -> novo cristal -> novo selo -> revalidação` ainda não é automático.
- Validação e versão do conceito usam ficheiros atómicos separados; uma falha
  entre ambos pode deixar um relatório órfão auditável, nunca uma promoção sem
  relatório.
- `CRYSTALLIZED` exige no futuro validações independentes e ainda não pode ser
  escrito.
