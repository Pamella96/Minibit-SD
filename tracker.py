import flask
import random
import threading
import logging

# Configuração básica do sistema de logs para exibir mensagens no terminal.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Variáveis Globais ---
TOTAL_DE_BLOCOS = 50                 # O número total de blocos que compõem o ficheiro.
peers_ativos = {}                    # Dicionário para armazenar os peers ativos e os seus endereços. Ex: {'peer_1': 'http://127.0.0.1:5001'}.
blocos_dos_peers = {}                # Dicionário que mapeia cada peer aos blocos que ele possui.
lock = threading.Lock()              # Lock para garantir o acesso seguro às estruturas de dados partilhadas em ambiente com múltiplas threads.
blocos_do_rastreador = set(range(TOTAL_DE_BLOCOS))     # O rastreador conhece todos os blocos para a distribuição inicial.
blocos_nao_distribuidos = set(range(TOTAL_DE_BLOCOS)) # Conjunto para controlar os blocos que ainda não foram entregues a nenhum peer.

# Inicializa a aplicação Flask.
app = flask.Flask(__name__)

def obter_peers_aleatorios(id_peer_solicitante, num_peers=5):
    """
    Retorna uma lista de peers aleatórios da rede, excluindo o próprio solicitante.
    Se a rede tiver menos de `num_peers` (além do solicitante), retorna todos os peers disponíveis.
    """
    with lock:
        # Cria uma lista com todos os IDs de peers, exceto o que fez o pedido.
        peers_disponiveis = [pid for pid in peers_ativos if pid != id_peer_solicitante]
        
        # Se houver poucos peers, retorna todos os que estão disponíveis.
        if len(peers_disponiveis) < num_peers:
            return {pid: peers_ativos[pid] for pid in peers_disponiveis}
        # Caso contrário, seleciona uma amostra aleatória.
        else:
            ids_peers_aleatorios = random.sample(peers_disponiveis, num_peers)
            return {pid: peers_ativos[pid] for pid in ids_peers_aleatorios}

@app.route('/register', methods=['POST'])
def registrar_peer():
    """
    Endpoint para registar um novo peer na rede.
    O rastreador distribui um conjunto inicial de blocos, garantindo que todos os blocos
    sejam eventualmente disponibilizados na rede.
    """
    dados = flask.request.json
    id_peer = dados['peer_id']
    endereco_peer = dados['address']
    
    with lock:
        # Só regista o peer se ele não for já conhecido.
        if id_peer not in peers_ativos:
            peers_ativos[id_peer] = endereco_peer
            
            num_blocos_para_entregar = min(10, TOTAL_DE_BLOCOS)
            blocos_iniciais = []

            # LÓGICA CRÍTICA: Prioriza a distribuição de blocos que ainda não estão na rede.
            if blocos_nao_distribuidos:
                # Calcula quantos blocos não distribuídos pode entregar.
                num_a_atribuir = min(num_blocos_para_entregar, len(blocos_nao_distribuidos))
                blocos_para_atribuir = random.sample(list(blocos_nao_distribuidos), k=num_a_atribuir)
                
                # Atualiza o conjunto de blocos não distribuídos, removendo os que acabaram de ser entregues.
                for bloco in blocos_para_atribuir:
                    blocos_nao_distribuidos.remove(bloco)
                blocos_iniciais = blocos_para_atribuir
            # Se todos os blocos já foram distribuídos pelo menos uma vez, entrega um conjunto totalmente aleatório.
            else:
                logging.info("Todos os blocos já foram distribuídos. Fornecendo conjunto aleatório.")
                blocos_iniciais = random.sample(list(blocos_do_rastreador), k=num_blocos_para_entregar)

            # Armazena os blocos que o novo peer possui.
            blocos_dos_peers[id_peer] = set(blocos_iniciais)
            logging.info(f"Peer {id_peer} registado com {len(blocos_iniciais)} blocos iniciais.")
            logging.info(f"{len(blocos_nao_distribuidos)} blocos restantes para a distribuição inicial.")
        
    # Retorna o estado do registo e as informações necessárias para o peer.
    return flask.jsonify({
        'status': 'registered',
        'initial_blocks': list(blocos_dos_peers.get(id_peer, [])),
        'total_blocks': TOTAL_DE_BLOCOS
    })

@app.route('/get_peers', methods=['GET'])
def obter_peers():
    """Endpoint para um peer obter uma lista de outros peers ativos."""
    id_peer = flask.request.args.get('peer_id')
    if not id_peer:
        return flask.jsonify({'error': 'peer_id é obrigatório'}), 400
        
    lista_de_peers = obter_peers_aleatorios(id_peer)
    return flask.jsonify(lista_de_peers)

@app.route('/get_block_info', methods=['POST'])
def obter_info_blocos():
    """
    Endpoint que retorna quais peers possuem um determinado conjunto de blocos.
    Esta informação é crucial para a estratégia 'Rarest First' do peer.
    """
    dados = flask.request.json
    ids_dos_blocos = dados.get('block_ids', [])
    donos_dos_blocos = {}
    
    with lock:
        for id_bloco in ids_dos_blocos:
            # Encontra todos os peers que possuem o bloco, EXCLUINDO o próprio rastreador da lista.
            donos = [pid for pid, blocos in blocos_dos_peers.items() if id_bloco in blocos and pid != 'tracker']
            donos_dos_blocos[str(id_bloco)] = donos
            
    return flask.jsonify(donos_dos_blocos)

@app.route('/update_blocks', methods=['POST'])
def atualizar_blocos():
    """Endpoint para um peer informar ao rastreador que adquiriu novos blocos."""
    dados = flask.request.json
    id_peer = dados['peer_id']
    novos_blocos = set(dados['blocks'])
    
    with lock:
        if id_peer in blocos_dos_peers:
            # Adiciona os novos blocos ao conjunto de blocos do peer.
            blocos_dos_peers[id_peer].update(novos_blocos)
            logging.info(f"Peer {id_peer} atualizou. Total de blocos agora: {len(blocos_dos_peers[id_peer])}")
        else:
            return flask.jsonify({'status': 'error', 'message': 'Peer não registado'}), 404
            
    return flask.jsonify({'status': 'updated'})

# Ponto de entrada do script.
if __name__ == '__main__':
    # Define que a entidade 'tracker' possui todos os blocos (apenas para referência interna).
    blocos_dos_peers['tracker'] = blocos_do_rastreador
    logging.info(f"Rastreador iniciado com {len(blocos_do_rastreador)} blocos. Aguardando peers para distribuição inicial...")
    # Inicia o servidor Flask. 'use_reloader=False' é importante para evitar que o script reinicie e perca as variáveis em memória.
    app.run(port=5000, debug=True, use_reloader=False)
