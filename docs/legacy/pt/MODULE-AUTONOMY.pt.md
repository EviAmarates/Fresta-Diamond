# Diamond — autonomia limitada de módulos

Estado: **primeiro corte implementado; apenas diagnóstico e desenho não executável**.

## Objetivo

Quando um objetivo termina com um `MISSING_CAPABILITY`, o Diamond pode avaliar
se a lacuna deve ser resolvida por reutilização, composição ou por um novo
módulo. A LLM participa na decisão sem receber autoridade para escrever código,
instalar, admitir ou ativar o módulo.

```text
lacuna observada
  -> inventário de operações existentes
  -> provider exato? NO_NEW_MODULE determinístico
  -> análise O1/O2/O3 pela LLM
  -> NO_NEW_MODULE | PROPOSE_MODULE
  -> preflight anti-entropia do desenho
  -> proposta ou rejeição arquivada de forma imutável
```

## Linguagem das três ordens

- **O1** declara os outcomes limitados que a operação teria de produzir.
- **O2** explica por que reutilização/composição é insuficiente e enumera as
  dependências necessárias.
- **O3** fixa restrições e condições observáveis de conclusão.

Estas ordens são relativas ao objetivo. Não transformam um módulo em O1, O2 ou
O3 universal e não provam verdade semântica.

## Fronteiras de autoridade

- A camada é fixada pelo host como `BELOW_CONTROLLER`.
- A capability e os schemas são fixados pelo pedido; a LLM não os pode trocar.
- Efeitos e permissões propostos têm de ser subconjuntos das listas fornecidas
  pelo host. As listas são vazias por defeito.
- O preflight reutiliza a política anti-entropia, mas **não equivale à admissão
  real** de um módulo implementado.
- O artefacto tem autoridade `UNVALIDATED_MODULE_DESIGN`.
- O resultado declara explicitamente `executable_code_created=false` e
  `module_enabled=false`.
- Propostas rejeitadas não são apagadas: ficam arquivadas com remainders para
  futura aprendizagem Φ−.

O sistema bloqueia propostas que tentem substituir ou contornar controller,
Gatekeepers, EffectBroker, blueprints ou fronteiras constitucionais.

## Comandos

```text
/module suggest --output-schema SCHEMA CAPABILITY OBJECTIVE
/module proposals
/module inspect SUGGESTION_ID
```

Integrações estruturadas podem ainda fornecer `input_schemas`,
`occurrence_count`, `allowed_effects` e `allowed_permissions` através de
`DiamondCommandService.invoke()`. A linha textual mantém deliberadamente uma
superfície menor.

## Limitações honestas

- O inventário nativo é atualmente montado explicitamente pela aplicação,
  porque os registries de execução são efémeros. Um catálogo durável virá
  depois.
- Compatibilidade de schema cria apenas candidatos de reutilização; não prova
  que uma composição serve o objetivo.
- A LLM pode tomar uma decisão conservadora ou justificar mal uma lacuna. O
  arquivo preserva o resultado para comparação, sem lhe conceder autoridade.
- Ainda não existem scaffold, geração de código, sandbox de testes, assinatura,
  instalação, admissão real ou enable autónomo.

## Próximo corte futuro

Só depois de existir uma sandbox forte: transformar uma proposta aprovada num
scaffold isolado, gerar testes a partir dos outcomes O1/O2/O3, executar sem
autoridade persistente e submeter o resultado ao fluxo normal de descoberta e
admissão. Nenhuma destas fases deve ser fundida com a decisão de proposta.
