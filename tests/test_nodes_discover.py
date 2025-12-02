import multiprocessing as mp
import random
import time

import pylancom


def start_test_node():
    try:
        node_name = "TestDiscoverNode"
        print(f"Starting node {node_name}")
        node = pylancom.init_node(node_name, "127.0.0.1")
        node.spin()
        print(f"Node {node_name} stopped")
    except KeyboardInterrupt:
        node.stop_node()
        print(f"Node {node_name} stopped")


def start_node_task(num: int):
    try:
        node_name = f"Node_{num}"
        print(f"Starting node {node_name}")
        node = pylancom.init_node(node_name, "127.0.0.1")
        node.spin()
        print(f"Node {node_name} stopped")
    except KeyboardInterrupt:
        node.stop_node()
        print(f"Node {node_name} stopped")


if __name__ == "__main__":
    node_tasks: list[mp.Process] = []
    # test_node_task = mp.Process(target=start_test_node)
    # node_tasks.append(test_node_task)
    # test_node_task.start()
    try:
        for i in range(2):
            task = mp.Process(target=start_node_task, args=(i,))
            task.start()
            node_tasks.append(task)
            time.sleep(random.random())
        print("All nodes have been started")
        for task in node_tasks:
            task.join()
    except KeyboardInterrupt:
        for task in node_tasks:
            task.terminate()
        print("All nodes have been terminated")