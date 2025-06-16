import requests
import threading
import time
import random
import logging
from flask import Flask, request, jsonify

# URL base do servidor rastreador (tracker).
URL_RASTREADOR = 'http://127.0.0.1:5000'

class Peer:
    """Representa um cliente na rede de compartilhamento de arquivos."""
    
    def __init__(self, id_peer, porta):
        """Inicializa um novo peer."""
        self.id_peer = id_peer
        self.endereco = f'http://127.0.0.1:{porta}'
        self.meus_blocos = set()                 # Conjunto de IDs dos blocos que o peer possui.
        self.total_de_blocos = -1                # Número total de blocos que compõem o arquivo.
        self.peers_conhecidos = {}               # Dicionário de peers na rede {id_peer: endereco}.
        self.peers_desbloqueados = set()         # Conjunto de peers para os quais este peer fará upload (unchoke fixo).
        self.peer_otimista_desbloqueado = None   # Peer escolhido aleatoriamente para upload (unchoke otimista).
        self.semeando = False                    # Torna-se True quando o peer tem todos os blocos.
        self.lock = threading.Lock()             # Lock para garantir a segurança em operações concorrentes.

        # Configuração do sistema de logs para exibir mensagens no console.
        self.log = logging.getLogger(self.id_peer)
        manipulador = logging.StreamHandler()
        formatador = logging.Formatter(f'%(asctime)s - {self.id_peer} - %(levelname)s - %(message)s')
        manipulador.setFormatter(formatador)
        if not self.log.handlers:
            self.log.addHandler(manipulador)
        self.log.setLevel(logging.INFO)

        # Também salvar os logs em arquivo
        arquivo_log = logging.FileHandler(f'{self.id_peer}.log', mode='a', encoding='utf-8')
        arquivo_log.setFormatter(formatador)
        self.log.addHandler(arquivo_log)

        self.log.setLevel(logging.INFO)

        # Inicia um servidor Flask para responder a requisições de outros peers.
        self.app = Flask(__name__)
        self.configurar_rotas()

    def configurar_rotas(self):
        
        # Rota para que outros peers possam solicitar um bloco.
        @self.app.route('/request_block/<int:id_bloco>', methods=['GET'])
        def servir_bloco(id_bloco):
            id_peer_solicitante = request.args.get('peer_id')
            with self.lock:
                # Caso 1: O peer já completou o download (está semeando).
                if self.semeando:
                    if id_bloco in self.meus_blocos:
                        self.log.info(f"Semeando: Enviando bloco {id_bloco} para {id_peer_solicitante}")
                        return jsonify({'block_id': id_bloco, 'data': f'Dados do bloco {id_bloco}'})
                    else:
                        return jsonify({'error': 'Bloco não encontrado'}), 404

                # Caso 2: O peer ainda está baixando. Aplica a lógica de unchoke.
                # Verifica se o solicitante está na lista de desbloqueados ou é o otimista.
                esta_desbloqueado = id_peer_solicitante in self.peers_desbloqueados or id_peer_solicitante == self.peer_otimista_desbloqueado
                
                if not esta_desbloqueado:
                    self.log.warning(f"Rejeitando pedido do bloco {id_bloco} de {id_peer_solicitante} (choked).")
                    return jsonify({'error': 'choked'}), 403

                # Se estiver desbloqueado, envia o bloco.
                if id_bloco in self.meus_blocos:
                    self.log.info(f"Enviando bloco {id_bloco} para {id_peer_solicitante}")
                    return jsonify({'block_id': id_bloco, 'data': f'Dados do bloco {id_bloco}'})
                else:
                    return jsonify({'error': 'Bloco não encontrado'}), 404

    def executar_app_flask(self, porta):
        """Executa o servidor Flask em uma thread separada para não bloquear o programa principal."""
        self.app.run(port=porta, debug=False)

    def mostrar_blocos(self):
        with self.lock:
            blocos_ordenados = sorted(self.meus_blocos)
            self.log.info(f"Blocos atuais ({len(blocos_ordenados)}/{self.total_de_blocos}): {blocos_ordenados}")    

    def registrar_no_rastreador(self):
        """Envia uma requisição de registro para o tracker e recebe os blocos iniciais."""
        try:
            dados_envio = {'peer_id': self.id_peer, 'address': self.endereco}
            resposta = requests.post(f'{URL_RASTREADOR}/register', json=dados_envio, timeout=5)
            if resposta.status_code == 200:
                dados = resposta.json()
                self.meus_blocos = set(dados['initial_blocks'])
                self.total_de_blocos = dados['total_blocks']
                self.log.info(f"Registrado com sucesso. Recebi {len(self.meus_blocos)} blocos. Total na rede: {self.total_de_blocos}")
                self.mostrar_blocos() # Chamada para mostrar os blocos atuais no console
                return True
        except requests.exceptions.RequestException as e:
            self.log.error(f"Não foi possível registrar no rastreador: {e}")
        return False

    def atualizar_peers_conhecidos(self):
        """Solicita ao tracker uma lista de outros peers ativos na rede."""
        try:
            parametros = {'peer_id': self.id_peer}
            resposta = requests.get(f'{URL_RASTREADOR}/get_peers', params=parametros, timeout=5)
            if resposta.status_code == 200:
                with self.lock:
                    self.peers_conhecidos.update(resposta.json())
        except requests.exceptions.RequestException as e:
            self.log.error(f"Não foi possível obter a lista de peers: {e}")

    def selecionar_bloco_mais_raro(self):
        """Implementa a estratégia 'Rarest First' para escolher qual bloco baixar."""
        blocos_faltantes = list(set(range(self.total_de_blocos)) - self.meus_blocos)
        if not blocos_faltantes:
            return None, None

        try:
            # Pede ao tracker a informação de quais peers possuem os blocos faltantes.
            resposta = requests.post(f'{URL_RASTREADOR}/get_block_info', json={'block_ids': blocos_faltantes}, timeout=5)
            if resposta.status_code == 200:
                raridade_blocos = resposta.json()
                
                # Filtra blocos que podem não estar disponíveis em nenhum peer.
                raridade_valida = {k: v for k, v in raridade_blocos.items() if v}
                if not raridade_valida:
                    return None, None

                # Encontra o ID do bloco que é possuído pelo menor número de peers.
                id_bloco_mais_raro_str = min(raridade_valida, key=lambda b: len(raridade_valida[b]))
                id_bloco_mais_raro = int(id_bloco_mais_raro_str)

                # Dentre os peers que possuem o bloco mais raro, seleciona aqueles que este peer conhece.
                fontes_potenciais = [p for p in raridade_valida[id_bloco_mais_raro_str] if p in self.peers_conhecidos]

                if not fontes_potenciais:
                    return None, None

                # Escolhe uma fonte aleatória entre as potenciais.
                id_peer_fonte = random.choice(fontes_potenciais)
                return id_bloco_mais_raro, id_peer_fonte
        except requests.exceptions.RequestException as e:
            self.log.error(f"Erro ao consultar a raridade do bloco: {e}")
        return None, None

    def solicitar_bloco(self, id_bloco, id_peer_fonte):
        """Envia uma requisição a outro peer para obter um bloco específico."""
        try:
            endereco_fonte = self.peers_conhecidos.get(id_peer_fonte)
            if not endereco_fonte:
                self.log.error(f"Endereço do peer {id_peer_fonte} não encontrado.")
                return False
                
            parametros = {'peer_id': self.id_peer}
            resposta = requests.get(f'{endereco_fonte}/request_block/{id_bloco}', params=parametros, timeout=5)

            if resposta.status_code == 200:
                dados = resposta.json()
                with self.lock:
                    self.meus_blocos.add(dados['block_id'])
                self.log.info(f"Sucesso! Bloco {id_bloco} recebido de {id_peer_fonte}. Total: {len(self.meus_blocos)}/{self.total_de_blocos}")
                # Informa ao tracker que agora possui um novo bloco.
                requests.post(f'{URL_RASTREADOR}/update_blocks', json={'peer_id': self.id_peer, 'blocks': list(self.meus_blocos)})
                return True
            elif resposta.status_code == 403:
                self.log.warning(f"Pedido do bloco {id_bloco} para {id_peer_fonte} negado (choked).")
            else:
                self.log.error(f"Falha ao obter o bloco {id_bloco} de {id_peer_fonte}. Status: {resposta.status_code}")
        except requests.exceptions.RequestException as e:
            self.log.error(f"Erro de conexão ao solicitar bloco de {id_peer_fonte}: {e}")
        return False

    def olho_por_olho_e_unchoke_otimista(self):
        """Gerencia as lógicas de 'tit-for-tat' e 'optimistic unchoke' em uma thread separada."""
        while len(self.meus_blocos) < self.total_de_blocos:
            # A cada 10 segundos, faz o 'optimistic unchoke'.
            time.sleep(10)
            with self.lock:
                # Escolhe um peer aleatório que não esteja na lista de desbloqueados fixos.
                potenciais_otimistas = [p for p in self.peers_conhecidos if p not in self.peers_desbloqueados]
                if potenciais_otimistas:
                    self.peer_otimista_desbloqueado = random.choice(potenciais_otimistas)
                    self.log.info(f"Unchoke otimista: {self.peer_otimista_desbloqueado}")

            # A cada 20 segundos (10s aqui + 10s acima), reavalia os 4 melhores peers (tit-for-tat).
            time.sleep(10)
            blocos_faltantes = list(set(range(self.total_de_blocos)) - self.meus_blocos)
            if not blocos_faltantes:
                continue

            pontuacoes_peers = {}
            try:
                # Pede ao tracker a lista de donos dos blocos faltantes.
                resposta = requests.post(f'{URL_RASTREADOR}/get_block_info', json={'block_ids': blocos_faltantes}, timeout=5)
                if resposta.status_code == 200:
                    donos_dos_blocos = resposta.json()
                    # Calcula uma pontuação para cada peer com base nos blocos raros que ele possui.
                    for id_peer in self.peers_conhecidos:
                        pontuacao = sum(1 for id_bloco in blocos_faltantes if id_peer in donos_dos_blocos.get(str(id_bloco), []) and len(donos_dos_blocos.get(str(id_bloco), [])) < 3)
                        pontuacoes_peers[id_peer] = pontuacao
            except requests.exceptions.RequestException:
                self.log.error("Não foi possível obter info de blocos para o Tit-for-Tat.")
                continue

            # Ordena os peers pela pontuação e seleciona os 4 melhores.
            peers_ordenados = sorted(pontuacoes_peers.items(), key=lambda item: item[1], reverse=True)
            with self.lock:
                self.peers_desbloqueados = {id_peer for id_peer, pontuacao in peers_ordenados[:4]}
                self.log.info(f"Peers desbloqueados (fixos): {self.peers_desbloqueados}")
        
        self.log.info("Thread de Choking/Unchoking encerrada pois o download foi concluído.")

    def iniciar(self):
        """Inicia a operação do peer: servidor, registro, threads e loop de download."""
        porta = int(self.endereco.split(':')[-1])
        # Inicia o servidor Flask em sua própria thread.
        thread_flask = threading.Thread(target=self.executar_app_flask, args=(porta,))
        thread_flask.daemon = True
        thread_flask.start()

        # Registra-se no tracker.
        if not self.registrar_no_rastreador():
            return

        # Obtém a lista inicial de peers.
        self.atualizar_peers_conhecidos()

        # Inicia a thread que gerencia a lógica de unchoke.
        thread_choking = threading.Thread(target=self.olho_por_olho_e_unchoke_otimista)
        thread_choking.daemon = True
        thread_choking.start()

        # Loop principal para baixar os blocos.
        while len(self.meus_blocos) < self.total_de_blocos:
            if self.total_de_blocos == -1: # Aguarda o registro ser concluído.
                time.sleep(1)
                continue

            # Atualiza a lista de peers conhecidos periodicamente.
            if random.randint(1, 10) == 1:
                self.atualizar_peers_conhecidos()

            # Seleciona e solicita o bloco mais raro.
            bloco_para_obter, peer_fonte = self.selecionar_bloco_mais_raro()
            if bloco_para_obter is not None and peer_fonte is not None:
                self.solicitar_bloco(bloco_para_obter, peer_fonte)
            else:
                # Aguarda se não houver blocos disponíveis para baixar.
                time.sleep(3)
            
            # Pausa para não sobrecarregar a rede.
            time.sleep(random.uniform(0.5, 2))

        # --- MODO DE SEEDING ---
        with self.lock:
            self.semeando = True
        self.log.info("--- ARQUIVO COMPLETO! ---")
        self.log.info(f"Todos os {self.total_de_blocos} blocos foram baixados. Entrando em modo de seeding.")

        # Mantém o peer vivo para continuar servindo blocos para outros.
        try:
            while True:
                time.sleep(60)
                self.log.info("Atuando como seeder...")
        except KeyboardInterrupt:
            self.log.info("Seeder encerrado manualmente.")


if __name__ == '__main__':
    import sys
    # Valida os argumentos da linha de comando.
    if len(sys.argv) != 3:
        print("Uso: python peer.py <id_peer> <porta>")
        sys.exit(1)

    id_peer_arg = sys.argv[1]
    porta_arg = int(sys.argv[2])

    # Cria e inicia a instância do Peer.
    peer = Peer(id_peer=id_peer_arg, porta=porta_arg)
    peer.iniciar()
