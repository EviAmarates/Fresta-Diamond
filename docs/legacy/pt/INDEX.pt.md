# Diamond — mapa da documentação

Este é o ponto de entrada para tudo o que pertence ao protótipo Diamond.

## Começar aqui

- [`../README.md`](../README.md) — objetivo do Diamond e relação com o Fresta Protocol.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — arquitetura modular e contratos de execução.
- [`STATUS.md`](STATUS.md) — estado implementado, testes e próximo corte.
- [`WORKLOG.md`](WORKLOG.md) — decisões e marcos de desenvolvimento.
- [`QWEN-RUNNER.md`](QWEN-RUNNER.md) — como executar o teste manual da LLM local.
- [`TEST-LAB.md`](TEST-LAB.md) — fixtures, baselines e comparação de regressões.
- [`LEARNING-MEMORY.md`](LEARNING-MEMORY.md) — commits atómicos, recuperação e políticas de retrieval.
- [`CONCEPTS.md`](CONCEPTS.md) — conceitos nativos, pertenças, hierarquia e limites do primeiro corte.
- [`CONCEPT-RESEARCH.md`](CONCEPT-RESEARCH.md) — gaps pesquisáveis, EffectBroker, source units e handoff obrigatório para `/learn`.
- [`CONCEPT-INTEGRATION.md`](CONCEPT-INTEGRATION.md) — `/learn` externo, cristais committed, reconhecimento e selos de proveniência.
- [`ATTENTION-MEMORY.md`](ATTENTION-MEMORY.md) — contextos ativos, suspensão, reativação, arquivo e abandono controlado.
- [`CHAT.md`](CHAT.md) — sessões persistentes, histórico selado e projeção do transcrito na atenção.
- [`MODULE-AUTONOMY.md`](MODULE-AUTONOMY.md) — lacunas, reutilização e propostas O1/O2/O3 sem criação nem ativação de código.

## Ontologia e integrações

- [`ONTOLOGY-BRIDGE.md`](ONTOLOGY-BRIDGE.md) — tradução operacional entre o kernel ontológico do Fresta e o runtime Diamond.
- [`ANTI-ENTROPY-KERNEL.md`](ANTI-ENTROPY-KERNEL.md) — proposta WIP para tornar a cláusula anti-entropia uma fronteira constitucional executável.
- [`CONSTITUTIONAL-FIREWALL.md`](CONSTITUTIONAL-FIREWALL.md) — contrato público e estado WIP da fronteira constitucional obrigatória.
- [`COGNITIVE-WORKSPACE.md`](COGNITIVE-WORKSPACE.md) — desenho WIP da mesa cognitiva, folhas, backlinks e promoção obrigatória através de `/learn`.
- [`COMMANDS.md`](COMMANDS.md) — registry e serviço headless partilhado por futuras interfaces REPL/Web.
- [`REPL.md`](REPL.md) — processo persistente fino, streams, erros e utilização da LLM local.
- [`PHI-MINUS-MEMORY.md`](PHI-MINUS-MEMORY.md) — proposta WIP de memória negativa produtiva, dupla fronteira e promoção segura de regras.
- [`INTEGRATIONS.md`](INTEGRATIONS.md) — papel futuro do Fresta EDGE, Fresta Finance e outros módulos recuperáveis.
- [`LEGACY-WORKLOG-EXTRACT.md`](LEGACY-WORKLOG-EXTRACT.md) — histórico integral migrado do bloco de notas global.

## Código

- [`../src/fresta_diamond`](../src/fresta_diamond) — implementação do runtime.
- [`../tests`](../tests) — testes isolados do Diamond.
- [`../testdata`](../testdata) — laboratório de dados isolados e runs arquivados.
- [`../scripts`](../scripts) — benchmarks e smokes especializados; não são interfaces públicas.
- [`../pyproject.toml`](../pyproject.toml) — configuração autónoma do pacote e dos testes.

## Autoridade documental

1. O kernel ontológico geral do Fresta continua em
   [`../../ONTOLOGICAL_KERNEL-v3-DRAFT.md`](../../ONTOLOGICAL_KERNEL-v3-DRAFT.md).
2. Este diretório contém a tradução e as decisões específicas do Diamond.
3. O código e os testes demonstram o comportamento atualmente implementado.
4. Ideias ainda não implementadas aparecem como `WIP`, não como garantias.

Novas notas específicas do Diamond devem ser guardadas aqui.
