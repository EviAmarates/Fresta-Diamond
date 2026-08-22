# Diamond — integrações e mecanismos recuperáveis

## Fresta EDGE

Repositório: [EviAmarates/fresta-edge](https://github.com/EviAmarates/fresta-edge)

O EDGE pode funcionar como gerador de lentes operacionais: recebe um domínio
delimitado e produz uma perspetiva temporária para atenção, conversa, `/learn` ou
pesquisa. Uma contra-lente pode procurar omissões e pressupostos.

Uma lente não é o conceito. O conceito indexa conhecimento relativamente estável;
a lente é uma projeção dependente do objetivo. Ordens fixas dentro da lente podem
ser adequadas ao domínio fechado. Noutro objetivo Diamond, os papéis voltam a ser
contextualizados.

Não migrar cegamente nomenclatura tratada como novas ordens, dependências de
interface/pesquisa, ausência de proveniência ou persistência direta de resultados.

## Fresta Finance

Repositório: [EviAmarates/fresta-finance](https://github.com/EviAmarates/fresta-finance)

As antigas designações O4/O5 representam sobretudo tipos ou profundidades de
segunda ordem, não ordens ontológicas adicionais.

Mecanismos recuperáveis incluem orçamentos adaptativos, checkpoints, retoma,
cache, invalidação, DAGs, proveniência, comparação de hipóteses e separação entre
recolha, análise e síntese.

Não migrar cegamente booleanos globais da LLM, acoplamento ao domínio financeiro,
nomenclatura incompatível ou factos externos sem estatuto epistémico.

## Pesquisa externa

A internet é fonte de candidatos, vocabulário, relações e evidência; não
autoridade automática.

1. formar o conceito com memória e dados presentes;
2. se faltar justificação, pesquisar pelo nome e pelo conjunto de características;
3. comparar fontes e proveniência;
4. validar os candidatos pelas mesmas três ordens;
5. guardar apenas o resultado e estatuto permitidos pela evidência.

Pesquisar características permite reconhecer equivalências computacionais e
conceitos com nomes diferentes.

O primeiro corte Diamond está implementado em `concept_research.py`: gaps
explícitos geram queries neutral-first, `internet.search` passa pelo
`EffectBroker`, e resultados tornam-se source units sem autoridade no Cognitive
Workspace. O adapter inicial pesquisa a Wikipédia; fontes académicas e
diversidade automática continuam WIP.

## Regra de integração

EDGE, Finance, internet e futuros módulos são capacidades atrás de contratos. Não
controlam o kernel, não escrevem diretamente na memória e não criam novas ordens.
Chamadas externas atravessam o `EffectBroker`; persistência atravessa validação e
política explícitas.
