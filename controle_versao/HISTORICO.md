# Histórico do projeto — Classificação de Beneficiários do Programa

> ⚠️ **Arquivo gerado.** Não edite este `.md`: edite o `historico.json` e rode
> `python controle_versao/atualizar.py`. O que estiver escrito aqui à mão será perdido.

Anexo V — Painel de Monitoramento · Programa Luz para Todos / MME / ENBPar

| | |
|---|---|
| Versão exibida no rodapé | **V0.0.1002** |
| Última atualização | **2026-10-02** — Regra nova: equipamento público exige um e só um tipo (F9.5) |
| Período coberto | 2026-06-23 a 2026-10-02 |
| Tamanho | 9 fases, 47 sub-fases |
| Produção | https://monitoramentolpt.enbpar.gov.br |

## Como ler

Cada **fase** é um trecho da história com um tema próprio; cada **sub-fase** é um fato
datado dentro dela. O rótulo diz de que tipo é o fato:

- **Entrega** — Funcionalidade nova, disponível para quem usa o sistema
- **Decisão** — Escolha de rumo registrada, com o motivo
- **Correção** — Defeito encontrado e consertado
- **Incidente** — Algo quebrou em produção; fica registrado para não repetir
- **Segurança** — Redução de risco (segredo, permissão, exposição)
- **Infraestrutura** — Servidor, banco, rede, publicação
- **Dados** — Base de referência e cadastros

## F1 — Origem: o mock estático aprovado

*2026-06-23 a 2026-06-27 · concluída*

O projeto nasceu como uma tela sem backend, para os gestores aprovarem o fluxo antes de existir validação de verdade. Aprovado o visual, foi autorizado a virar um sistema real.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-06-23 | Entrega | **Primeiro commit: tela em React com validação simulada** — Front em React/Vite com o fluxo inteiro na tela (do login ao painel), mas sem backend: os resultados eram dados fixos, escritos à mão. |
| 2026-06-26 | Decisão | **Plano do backend finalizado** — Especificação de desenho do backend fechada (blocos A a G) antes de escrever código — foi o documento que guiou toda a V0. |
| 2026-06-27 | Decisão | **Aprovação para virar backend real** — O mock é aprovado e autorizado a se tornar aplicação funcional. Resíduos daquela fase sobrevivem no código como material morto (ex.: seedData.js). |

## F2 — V0: o sistema real entra no ar

*2026-06-30 a 2026-07-07 · concluída*

Em pouco mais de uma semana o backend passou a existir de verdade: login, filtro de acesso por empresa, validação da planilha contra a base de referência e envio do arquivo por e-mail. Entregue como V0, com etiqueta `v0` no histórico do código.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-06-30 | Entrega | **Primeira fase do backend pronta** — Estrutura do FastAPI no ar, com as camadas separadas: referência, acesso, leitura da planilha e validação. |
| 2026-07-01 | Entrega | **Login, senha e envio de e-mail** — Autenticação real (senha guardada como resumo criptográfico com sal, sessão assinada), troca obrigatória no primeiro acesso e os quatro tipos de e-mail do sistema. |
| 2026-07-07 | Entrega | **V0 entregue e no ar em gerenciador-gclt.com** — Produto completo em produção: fluxo de sete telas, validação real contra a base de referência, painel de inconsistências e relatório .csv baixado no navegador. 101 testes automatizados passando. *Primeira versão usável pelas sete empresas.* |

## F3 — As regras de validação endurecem

*2026-07-08 a 2026-07-22 · concluída*

Com o sistema em uso, cada planilha real revelou uma regra frouxa. Esta fase é uma sequência de decisões sobre o que bloqueia o envio (erro) e o que apenas avisa.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-07-09 | Decisão | **Regra da data de energização removida** — Exigir que a data caísse em 2026 recusava planilha legítima. Qualquer data passou a ser aceita; data em branco continua erro. |
| 2026-07-09 | Decisão | **A coluna “0 - Não é prioridade” passa a bloquear** — Duas cláusulas viraram erro: se a coluna é “Sim”, nenhuma outra tipologia pode estar marcada; se é “Não”, ao menos uma precisa estar. |
| 2026-07-09 | Decisão | **O arquivo-modelo passa a ter versão no nome** — O .xlsx oficial ganhou a data no nome, para nunca haver dúvida sobre qual versão o sistema serve e valida. |
| 2026-07-14 | Decisão | **A coluna “0” em branco vira erro** — Fechou o buraco da linha sem nada marcado, que até então passava em silêncio. |
| 2026-07-15 | Decisão | **Maiúsculas deixam de importar; acentos continuam importando** — “SIM” passou a valer como “Sim”. Já “NAO” sem acento segue inválido: o acento é parte do vocabulário do modelo oficial. |
| 2026-07-15 | Decisão | **Município e UF comparados por forma canônica** — “RORAINÓPOLIS” e “RORAINOPOLIS” passaram a ser o mesmo nome, e a sigla “AP” equivale a “Amapá”. Ruído de acento e espaço parou de gerar erro falso. |
| 2026-07-15 | Decisão | **Login por “operador” (solução temporária)** — O login por e-mail foi adiado; entrou um identificador por empresa, como `equatorialenergia` ou `energisa`. Decisão registrada como provisória. *É esta solução que o login canônico, em outubro, veio substituir.* |
| 2026-07-22 | Decisão | **Mensagens de erro passam a dizer o porquê** — Em vez de uma recusa genérica, a tela mostra o motivo concreto: qual empresa é dona do contrato, ou que o contrato não tem base de referência carregada. |

## F4 — Entrega à empresa e mudança para a Azure

*2026-07-16 a 2026-07-20 · concluída*

O projeto deixou de ser só do desenvolvedor: passou a ter um repositório da empresa, operado pela TI, e a produção migrou da VPS para a nuvem da Azure, em contêineres.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-07-17 | Decisão | **Documentos internos saem do código entregue** — O diário de bordo do projeto passou a ficar só na máquina local: a empresa recebe o sistema, não o registro de trabalho. Ele continua existindo e sendo escrito. |
| 2026-07-20 | Infraestrutura | **Produção passa a ser Azure com Docker, e o deploy fica automático** — Dois contêineres (a API e o site) numa máquina da Azure. A partir daqui, publicar código na linha principal dispara a atualização do ar sozinho. *Ganho de automação e, no mesmo movimento, o risco de publicar sem querer.* |

## F5 — Segunda rodada de regras e novos modelos oficiais

*2026-07-29 a 2026-08-28 · concluída*

O Ministério mudou o modelo duas vezes, e as regras de coerência entre colunas ganharam a forma final. Entrou também o marcador de versão no rodapé do site.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-07-29 | Decisão | **Tipo de comunidade exige a família correspondente** — Comunidade indígena obriga a marcar a família indígena, e assim por diante. A verificação passou de aviso a erro, e as demais famílias ficaram livres. |
| 2026-07-30 | Decisão | **Coordenadas dentro do Brasil e sem repetição** — Coordenada fora da faixa do país virou aviso; o mesmo par de coordenadas em duas linhas virou erro, porque duas casas não ocupam o mesmo ponto. |
| 2026-07-30 | Decisão | **Nenhuma célula em branco numa linha preenchida** — Todas as colunas de identificação e as 51 de tipologia passaram a ser obrigatórias. O achado sai uma vez por linha, nomeando as colunas vazias. *Uma ocorrência por célula daria 9.310 achados numa planilha real de 490 linhas.* |
| 2026-08-04 | Entrega | **O rodapé passa a mostrar a versão do produto** — Nasceu da dificuldade de saber se um deploy tinha de fato acontecido: o rodapé exibe `V0.0.0804`, atualizada a cada liberação. *É exatamente o lugar que este controle de versão vem alimentar.* |
| 2026-08-04 | Correção | **Resolvido o bug “a senha se perde”** — Em produção, senhas trocadas voltavam ao padrão. Causa confirmada: cada publicação substituía o arquivo de usuários pelo que vinha do repositório. |
| 2026-08-28 | Decisão | **Nova coluna CPF/CNPJ no modelo oficial** — O Ministério acrescentou a coluna no fim da planilha (de 52 para 53). Regra única: não pode ficar vazia — sem máscara e sem dígito verificador. |

## F6 — “Dado novo” deixa de bloquear o envio

*2026-09-16 a 2026-09-23 · concluída*

O sistema legado que alimenta a base de referência quebrou, e unidades recém-energizadas passaram a ser recusadas. A saída foi aceitar o dado novo como aviso, sob condição — e a condição teve de ser corrigida depois.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-09-16 | Decisão | **Unidade nova entra como aviso, não como erro** — Criada uma chave de configuração que transforma “não consta na referência” de erro em aviso, enquanto a base não é atualizada. |
| 2026-09-21 | Incidente | **Base publicada no lugar errado deixou um contrato recusando envio** — Os dados diários foram para o ramo de desenvolvimento em vez da linha principal; a produção respondeu “contrato sem base” até a correção. |
| 2026-09-22 | Decisão | **O aviso passa a ser a regra** — Antes era exceção ligada caso a caso; virou o comportamento padrão do sistema. Voltar ao erro passou a exigir decisão explícita. |
| 2026-09-23 | Correção | **A condição passa a ser medida por ODI, não pelo contrato inteiro** — A primeira versão exigia que a planilha trouxesse todas as unidades já cadastradas do contrato — impossível numa planilha mensal de 5 unidades contra uma base de 11.928. Passou a valer por ODI, mantendo a proteção contra erro de digitação. *A planilha do chamado foi de 5 erros para 0 erros e 5 avisos.* |
| 2026-09-23 | Decisão | **Banco único (MySQL), e proibido inventar outro** — Ficou vedado ao sistema criar um banco alternativo em arquivo local: sem conexão com o MySQL, ele falha com mensagem em vez de abrir um banco vazio onde ninguém vai procurar. |

## F7 — A primeira tentativa de trocar o login, e o que ela ensinou

*2026-09-28 a 2026-09-29 · concluída*

O login por e-mail com perfis foi levado à produção e teve de ser revertido no mesmo dia. A causa não era o código: era configuração ausente e um deploy que ficou congelado sem avisar. Dois dias que redesenharam o processo.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-09-28 | Incidente | **Reversão: o endereço do banco nunca existiu onde a produção lê** — Os dados do banco tinham sido digitados no servidor de teste, que é outra máquina. Todas as rotas de identidade responderam erro. |
| 2026-09-28 | Incidente | **Uma edição manual no servidor congelou todos os deploys** — A atualização morria em 8 segundos sem tocar no site, que seguia servindo a versão anterior. Nem a reversão chegou ao ar. O único sinal estava no painel de automação. *Regra que saiu daqui: o deploy não é a publicação do código, é o que a máquina efetivamente puxa — conferir o painel antes de concluir qualquer coisa.* |
| 2026-09-28 | Correção | **O deploy passa a sobrescrever o servidor, sem pedir licença** — A máquina de produção passou a ser forçada a ficar idêntica à linha principal, e edição manual lá é descartada — política que já estava implícita no desenho. |
| 2026-09-29 | Correção | **“Planilha enviada.” era mentira em produção** — A configuração publicada mantinha o envio em modo de ensaio: operadores das sete empresas viam sucesso e nada era entregue. Agora, se o envio não acontece e o modo de ensaio está desligado, a tela mostra o erro. *Falha silenciosa — a pior categoria: ninguém investiga o que parece ter dado certo.* |
| 2026-09-29 | Decisão | **Dados de negócio do e-mail saem do arquivo de segredos** — Servidor, remetente e lista de destinatários foram para um arquivo de parâmetros, lido a cada requisição. Trocar um destinatário deixou de exigir uma nova publicação. |

## F8 — O login canônico entra, e a segurança é endurecida

*2026-10-01 a 2026-10-01 · concluída*

Um único dia, com os pré-requisitos do post-mortem cumpridos um a um, terminando no merge bem-sucedido: a produção passou a ter login por e-mail corporativo com perfis, sobre o MySQL.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-10-01 | Decisão | **Dados do banco saem do arquivo de segredos** — No arquivo de segredos ficou só a senha; o resto foi para um arquivo de parâmetros, como fonte única. A variável antiga deixou de ser lida. |
| 2026-10-01 | Segurança | **Auditoria de segurança das três linhas de código** — Conclusão: as falhas típicas de desenvolvimento apressado não são o problema deste projeto. Os furos reais são os segredos versionados no repositório. |
| 2026-10-01 | Segurança | **O sistema deixa de criar tabela sozinho** — Antes, a primeira pessoa a usar o login criava as tabelas do banco. Agora o sistema apenas confere e reclama se faltar; criar virou comando rodado por uma pessoa, de propósito. *Tirou comandos de estrutura de banco do caminho do tráfego do site.* |
| 2026-10-01 | Segurança | **Diagnóstico pelo navegador, sem expor dado nenhum** — A página pública de saúde ficou mínima; o diagnóstico detalhado e o estado do banco passaram a exigir credencial. Sem terminal na máquina, é a única janela disponível. |
| 2026-10-01 | Segurança | **Sem chave de assinatura, o sistema não sobe** — Havia uma chave de exemplo embutida no código: sem configuração, o sistema assinava as sessões com um valor que qualquer pessoa com acesso ao repositório conhece. Agora ele falha na partida. |
| 2026-10-01 | Segurança | **Segredos deixam de aparecer em mensagem de erro** — Os três segredos passaram a ser objetos que se imprimem mascarados. Fechou um vazamento real, não hipotético: um erro de teste chegou a imprimir a chave inteira na tela. |
| 2026-10-01 | Decisão | **O “esqueci minha senha” antigo NÃO será consertado** — Ele reinicia a senha de qualquer operador para um valor público, sem autenticação. Decisão consciente: o login por operador será descontinuado, e existe uma chave que o desliga por inteiro. *Risco aceito e registrado, para ninguém “consertar” sem pedido.* |
| 2026-10-01 | Entrega | **Merge concluído: login por e-mail e perfis em produção** — Na segunda tentativa, com o banco conferido e a configuração no lugar certo, o login canônico entrou na linha principal e foi publicado. *A produção passou a autenticar por e-mail corporativo, com perfis e auditoria.* |
| 2026-10-01 | Infraestrutura | **Banco de produção inspecionado, e o firewall liberado** — Leitura pura do MySQL: as três tabelas existem, nenhuma de outro sistema, a conexão sai cifrada e o primeiro gerente já existe. O firewall foi liberado para a máquina de produção e para a estação de trabalho. |
| 2026-10-01 | Decisão | **O servidor de homologação é encerrado** — A VPS de teste sai do ar com o merge bem-sucedido e será reformatada, voltando em fases futuras, quando houver função nova para homologar. |

## F9 — Depois do merge: o e-mail de acesso e o controle de versão

*2026-10-01 — em aberto · em andamento*

Com o login novo no ar, apareceu o primeiro defeito de uso real — e começou o registro formal da história do projeto.

| Data | Tipo | O que aconteceu |
|---|---|---|
| 2026-10-01 | Correção | **O e-mail de criação de senha não saía** — O convite era gravado no banco e o e-mail nunca chegava, enquanto o e-mail da planilha funcionava. O remetente do convite vinha do arquivo de segredos, que havia perdido essa chave em 29/09 — valia então um endereço de domínio inexistente, que o servidor de e-mail não autoriza. *Cadastro e recuperação de senha estavam inutilizáveis desde o merge.* |
| 2026-10-02 | Entrega | **Pasta `controle_versao/` criada** — A história do projeto passa a ter registro próprio, em fases e sub-fases, com um arquivo legível por máquina para o rodapé do site mostrar a última atualização. |
| 2026-10-02 | Entrega | **O rodapé passa a ler a versão do backend** — A versão exibida deixou de ser uma constante escrita no código do front e passa a vir de `GET /api/versao`, que lê este arquivo do disco a cada pedido. O rodapé agora mostra a versão e a data da última atualização. *Fecha o que a F5.4 abriu em 04/08: o rodapé volta a ser marcador confiável de deploy — estava parado em V0.0.0804 havia dois meses.* |
| 2026-10-02 | Entrega | **Área do gerente e trilha de auditoria em produção** — Mergeada a branch da fase 2: perfil gerente, tela de administração de contas, trilha de auditoria com filtros e exportação em CSV/PDF, e a rota protegida que lê a trilha. Homologada à mão em setembro, antes de o servidor de teste ser encerrado. *O gerente passa a administrar contas e consultar quem fez o quê, sem depender de ninguém com acesso ao banco.* |
| 2026-10-02 | Decisão | **Regra nova: equipamento público exige um e só um tipo** — Quando o enquadramento descreve um equipamento público ou comunitário (8, 9, 10 ou 11), exatamente uma das 21 colunas de equipamento da planilha — escolas, unidades de saúde, poços, infraestrutura comunitária, associações, igrejas e projetos produtivos — deve estar marcada, e todas as demais não. Os mesmos enquadramentos passaram a exigir “Não” na coluna de prioridade. *A segunda parte não é detalhe: sem ela a linha ficaria impossível de preencher, com dois erros se contradizendo.* |
