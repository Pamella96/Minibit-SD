
# MiniBit - Sistema de Compartilhamento Cooperativo de Arquivos

MiniBit é um sistema distribuído de compartilhamento de arquivos entre múltiplos peers. Ele simula um ambiente P2P (peer-to-peer), onde os peers compartilham blocos de um arquivo de forma cooperativa, utilizando estratégias reais como **Rarest First** e uma versão simplificada de **Tit-for-Tat (Olho por Olho)**.

## 📌 Funcionalidades Principais

✅ Divisão do arquivo em blocos  
✅ Compartilhamento P2P entre múltiplos peers  
✅ Algoritmo **Rarest First** para priorizar blocos menos comuns  
✅ Estratégia **Tit-for-Tat (simplificada)** para decidir quem pode receber blocos  
✅ Tracker central para descoberta de peers  
✅ Sistema de logs para rastrear o progresso

## ⚙️ Requisitos

- Python 3.8+
- Dependências:  
  ```bash
  pip install -r requirements.txt
  ```

## 🗂️ Estrutura do Projeto

```
MiniBit/
├── peer.py              # Implementação de um peer (cliente P2P)
├── tracker.py           # Servidor central (tracker)
├── start_tracker.bat    # Script para iniciar o tracker no Windows
├── start_peers.bat      # Script para iniciar múltiplos peers no Windows
├── requirements.txt     # Dependências
└── README.md            # Este arquivo
```

## 🚀 Como Executar

### 1. Iniciar o Tracker
```bash
python tracker.py
```
Ou no Windows:
```bat
start_tracker.bat
```

### 2. Iniciar os Peers
```bash
python peer.py peer_1 5001
python peer.py peer_2 5002
```
Ou use:
```bat
start_peers.bat
```

## 🔄 Como Funciona

### 📁 Divisão em Blocos
O arquivo é virtualmente dividido em 50 blocos (`block_0`, `block_1`, ..., `block_49`).

### 📡 Registro no Tracker
- Registro via `/register`
- Recebimento de blocos iniciais
- Descoberta de outros peers via `/get_peers`

### 📉 Estratégia Rarest First
O peer prioriza o download dos blocos menos comuns, consultando o endpoint `/get_block_info` do tracker.

### 🔁 Tit-for-Tat Simplificado (Olho por Olho)
- 4 peers desbloqueados com mais blocos raros
- 1 peer desbloqueado otimista a cada 10s
- Apenas peers desbloqueados podem receber blocos

### 🧩 Encerramento
Peers que completam o arquivo entram em **modo seeder** e continuam compartilhando blocos.

## 💬 Protocolo de Comunicação

| Endpoint               | Método | Descrição                                            |
|------------------------|--------|------------------------------------------------------|
| `/register`            | POST   | Registro de peer e entrega de blocos iniciais       |
| `/get_peers`           | GET    | Lista de peers ativos (excluindo o solicitante)     |
| `/get_block_info`      | POST   | Quais peers possuem determinados blocos             |
| `/update_blocks`       | POST   | Atualiza os blocos que o peer possui                |
| `/request_block/<id>`  | GET    | Solicita bloco diretamente a outro peer             |

## 📊 Logs e Monitoramento

Os logs mostram:
- Blocos recebidos
- Peers desbloqueados
- Requisições rejeitadas (choked)
- Início do modo seeding

## 🔄 Exemplo de Fluxo de Comunicação

1. Peer A se registra no tracker e recebe blocos 0–9.
2. Peer B se registra e recebe blocos 10–19.
3. Peer A consulta `/get_peers` e descobre o Peer B.
4. Peer A usa `/get_block_info` para saber que o bloco 12 está com o Peer B.
5. Peer A faz uma requisição direta para `/request_block/12` no Peer B.
6. Peer B verifica se A está desbloqueado (Tit-for-Tat) e, se sim, envia o bloco.

## 🧪 Testes Sugeridos

- Teste com 3 a 10 peers
- Medir tempo de download total
- Análise dos logs: número de mensagens e blocos trocados

## 🧠 Reflexão

Este projeto demonstra, na prática, conceitos de redes peer-to-peer, coordenação descentralizada e algoritmos de compartilhamento. Estratégias como *Rarest First* e *Tit-for-Tat* garantem eficiência na distribuição mesmo em ambientes simulados.

## 🛠️ Melhorias Futuras

- Persistência do estado
- Testes em múltiplas máquinas (rede real)
- Criptografia das mensagens
- Suporte a múltiplos arquivos


