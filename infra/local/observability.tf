provider "helm" {
  kubernetes = {
    config_path    = abspath("${path.module}/../../data/platform/kubeconfig")
    config_context = "agentic-devops"
  }
}

resource "helm_release" "observability" {
  name        = "lab-observability"
  namespace   = kubernetes_namespace_v1.lab["lab-observability"].metadata[0].name
  chart       = abspath("${path.module}/../../charts/observability")
  wait        = true
  timeout     = 480
  max_history = 3
  values = [yamlencode({
    images = jsondecode(file("${path.module}/../../config/observability-images.json"))
    configs = { for name in ["collector", "prometheus", "tempo", "grafana"] :
      name => file("${path.module}/../../observability/${name}.yaml")
    }
    dashboard = file("${path.module}/../../observability/dashboard.json")
  })]
  depends_on = [kubernetes_network_policy_v1.telemetry_ingress, kubernetes_network_policy_v1.telemetry_egress,
  kubernetes_resource_quota_v1.lab, kubernetes_limit_range_v1.lab]
}

locals {
  telemetry_endpoints = merge(local.endpoints, {
    collector = "lab-observability", prometheus = "lab-observability",
    tempo     = "lab-observability", grafana = "lab-observability"
  })
  telemetry_connections = merge(
    { for name in ["api", "worker", "tools", "orders"] : "${name}-collector" => { source = name, target = "collector", port = 4318 } },
    { for name in ["api", "worker", "tools", "orders"] : "prometheus-${name}" => { source = "prometheus", target = name, port = 9090 } },
    { collector-tempo    = { source = "collector", target = "tempo", port = 4317 },
      grafana-prometheus = { source = "grafana", target = "prometheus", port = 9090 },
    grafana-tempo = { source = "grafana", target = "tempo", port = 3200 } }
  )
}

resource "kubernetes_network_policy_v1" "telemetry_egress" {
  for_each = local.telemetry_connections
  metadata {
    name      = "allow-${each.key}-egress"
    namespace = kubernetes_namespace_v1.lab[local.telemetry_endpoints[each.value.source]].metadata[0].name
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
          match_labels = { "kubernetes.io/metadata.name" = local.telemetry_endpoints[each.value.target] }
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

resource "kubernetes_network_policy_v1" "telemetry_ingress" {
  for_each = local.telemetry_connections
  metadata {
    name      = "allow-${each.key}-ingress"
    namespace = kubernetes_namespace_v1.lab[local.telemetry_endpoints[each.value.target]].metadata[0].name
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
          match_labels = { "kubernetes.io/metadata.name" = local.telemetry_endpoints[each.value.source] }
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
