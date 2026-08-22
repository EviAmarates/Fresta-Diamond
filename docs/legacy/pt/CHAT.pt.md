# Diamond — chat persistente

Estado: **primeiro corte vertical implementado; perfis, reflexão pós-turno e
pedidos naturais de módulos ainda WIP**.

## Objetivo

O chat é uma fachada persistente sobre mecanismos Diamond existentes. Não é uma
segunda memória nem uma pipeline cognitiva escondida:

```text
chat start
  -> retrieval relativo ao objetivo (quando existem candidatos)
  -> contexto de atenção
  -> folha-transcrito ativa
  -> binding de sessão selado

chat say
  -> mensagem USER persistida
  -> projeção na folha ativa
  -> attention turn + firewall/controller
  -> resposta ASSISTANT persistida
  -> projeção da resposta quando o contexto permanece ativo
```

## Três autoridades separadas

1. `AtomicChatStore` é o histórico canónico da conversa. Guarda a ligação da
   sessão e uma cadeia de mensagens verificável por SHA-256.
2. A folha-transcrito é a projeção de trabalho usada pela atenção. Continua
   `DRAFT` e não confirma o conteúdo que contém.
3. Memória de aprendizagem, perfil do utilizador e personalidade do assistente
   permanecem separados. Uma mensagem nunca é promovida só porque ocorreu no
   chat.

Mensagens do utilizador usam `USER_MESSAGE_ONLY`. Respostas usam
`MODEL_RESPONSE_UNVALIDATED`. O store rejeita autoridade incompatível com o
papel, IDs repetidos, alterações de sequência, mudança de sessão e adulteração
da cadeia.

## Pasta dedicada

Cada `DiamondApplication(data_root, ...)` usa `data_root/chat/`. A sessão fica
num diretório derivado por hash do ID; o binding é selado e as mensagens formam
uma cadeia própria. A workspace e a atenção continuam nos seus stores nativos.

## Comandos

```text
/chat start [--scope SCOPE] [--summary TEXT] [--budget N]
            [--batch-budget N] OBJECTIVE
/chat say [--budget N] SESSION_ID MESSAGE
/chat status SESSION_ID
/chat list
```

`start` e `say` podem chamar a LLM. `status` e `list` são offline. Quando não
existe qualquer candidato no scope, o host inicia atenção vazia sem chamar a
LLM para fabricar `NO_SELECTION`.

## Limites honestos deste corte

- Retrieval semântico ocorre no início da sessão, não automaticamente em cada
  mensagem.
- Ainda só pode existir um contexto foreground ACTIVE por instância.
- Se uma resposta for produzida no mesmo turno que provoca sleep, o chat store
  preserva-a, mas a folha ativa pode ficar uma revisão atrás até uma futura
  sincronização de retoma.
- O histórico é selado mas não encriptado; ainda não existe política de
  retenção/redação para conversas sensíveis.
- Não existem ainda `/chat resume`, archive, abandon ou troca de foreground.
- Não existem perfil do utilizador, personalidade evolutiva, reflexão
  pós-turno, `/remember` ou routing natural para `module.suggest`.

Estas limitações impedem apresentar o chat como completo ou pronto para Web,
mas o primeiro percurso start → say → histórico já é persistente e usa o mesmo
serviço central que as futuras interfaces.
