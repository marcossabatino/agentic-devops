locals {
  endpoints = {
    api      = "lab-app"
    worker   = "lab-app"
    tools    = "lab-tools"
    orders   = "lab-tools"
    postgres = "lab-data"
    migrate  = "lab-data"
  }
  connections = {
    api-database     = { source = "api", target = "postgres", port = 5432 }
    worker-database  = { source = "worker", target = "postgres", port = 5432 }
    worker-tools     = { source = "worker", target = "tools", port = 8080 }
    tools-database   = { source = "tools", target = "postgres", port = 5432 }
    tools-orders     = { source = "tools", target = "orders", port = 8080 }
    orders-database  = { source = "orders", target = "postgres", port = 5432 }
    migrate-database = { source = "migrate", target = "postgres", port = 5432 }
  }
}

resource "kubernetes_network_policy_v1" "default_deny" {
  for_each = local.namespaces
  metadata {
    name      = "default-deny"
    namespace = kubernetes_namespace_v1.lab[each.key].metadata[0].name
    labels    = local.labels
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}

resource "kubernetes_network_policy_v1" "dns" {
  for_each = local.namespaces
  metadata {
    name      = "allow-cluster-dns"
    namespace = kubernetes_namespace_v1.lab[each.key].metadata[0].name
    labels    = local.labels
  }
  spec {
    pod_selector {}
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = "kube-system" }
        }
        pod_selector {
          match_labels = { "k8s-app" = "kube-dns" }
        }
      }
      ports {
        protocol = "UDP"
        port     = "53"
      }
      ports {
        protocol = "TCP"
        port     = "53"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "egress" {
  for_each = local.connections
  metadata {
    name      = "allow-${each.key}-egress"
    namespace = kubernetes_namespace_v1.lab[local.endpoints[each.value.source]].metadata[0].name
    labels    = local.labels
  }
  spec {
    pod_selector {
      match_labels = { "app.kubernetes.io/name" = each.value.source }
    }
    policy_types = ["Egress"]
    egress {
      to {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = local.endpoints[each.value.target] }
        }
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = each.value.target }
        }
      }
      ports {
        protocol = "TCP"
        port     = each.value.port
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "ingress" {
  for_each = local.connections
  metadata {
    name      = "allow-${each.key}-ingress"
    namespace = kubernetes_namespace_v1.lab[local.endpoints[each.value.target]].metadata[0].name
    labels    = local.labels
  }
  spec {
    pod_selector {
      match_labels = { "app.kubernetes.io/name" = each.value.target }
    }
    policy_types = ["Ingress"]
    ingress {
      from {
        namespace_selector {
          match_labels = { "kubernetes.io/metadata.name" = local.endpoints[each.value.source] }
        }
        pod_selector {
          match_labels = { "app.kubernetes.io/name" = each.value.source }
        }
      }
      ports {
        protocol = "TCP"
        port     = each.value.port
      }
    }
  }
}
