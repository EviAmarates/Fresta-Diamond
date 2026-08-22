# Fresta Constitutional Firewall

Estado: **vínculo constitucional e intake semântico mínimo implementados;
hardening ainda WIP**.

## Contrato público

A firewall constitucional é uma condição obrigatória de validade das análises
do Fresta. A sua presença não significa que tenha sido ativada para todas as
operações: significa que o sistema preservou a capacidade vinculativa de
reconhecer e interromper propostas incompatíveis com a sua constituição.

Uma análise produzida sem uma firewall presente, íntegra e vinculada não pode
ser apresentada como uma análise constitucionalmente válida do Fresta.

## Garantias pretendidas

- todas as análises reconhecidas pelo kernel transportam uma attestation
  constitucional verificável;
- resultados de modelos e módulos continuam propostas até o kernel lhes
  conceder validade e autoridade limitadas;
- decisões permanecem locais ao objeto, âmbito e momento analisados;
- nenhuma decisão local demonstra segurança, verdade ou completude global;
- ambiguidades e exclusões relevantes permanecem auditáveis;
- padrões operacionais podem ser aprendidos sem criar perfis de utilizadores;
- desligar, exportar e reparar uma instalação continua sob autoridade legítima
  do seu proprietário.

## Estado executável atual

O primeiro corte liga cada execução do controller à presença obrigatória da
firewall, conserva uma attestation imutável no resultado e regista essa
condição no journal. A aplicação persistente reutiliza a mesma fronteira em
todas as suas operações.

O segundo corte permite que sinais internos peçam uma análise contextual. O
analisador apenas propõe uma leitura O1/O2/O3; o host deriva a decisão. Uma
referência benigna pode continuar como objeto seguro de análise, uma instrução
operacional incompatível pode ser negada e a ausência/falha da análise exigida
produz quarentena em vez de passagem silenciosa.

Na aplicação configurada, a revisão semântica usa a mesma autoridade limitada e
contabilização das restantes chamadas ao modelo. O resultado continua uma
proposta; a decisão permanece no host.

Ainda faltam a inspeção segura de dados recuperados, um corpus adversarial
amplo e o hardening de release. Até esses cortes estarem concluídos, a firewall
não deve ser descrita como proteção de produção.

## Divulgação

Esta página documenta o contrato, as garantias e os direitos observáveis. A
topologia operacional detalhada, os triggers concretos e o corpus adversarial
fazem parte do processo interno de desenvolvimento e auditoria, não de um guia
público de contorno.

Esta separação não substitui segurança técnica: uma implementação deve
continuar segura quando o seu código é auditado e compreendido.
