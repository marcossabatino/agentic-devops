terraform {
  required_version = "= 1.10.6"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "= 3.0.2"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "= 2.38.0"
    }
  }
}

provider "kubernetes" {
  config_path    = abspath("${path.module}/../../data/platform/kubeconfig")
  config_context = "agentic-devops"
}

locals {
  namespaces = toset(["lab-app", "lab-tools", "lab-data", "lab-observability"])
  labels = {
    "app.kubernetes.io/part-of"    = "agentic-devops"
    "app.kubernetes.io/managed-by" = "OpenTofu"
  }
}

resource "kubernetes_namespace_v1" "lab" {
  for_each = local.namespaces
  metadata {
    name = each.key
    labels = merge(local.labels, {
      "pod-security.kubernetes.io/enforce"         = "restricted"
      "pod-security.kubernetes.io/enforce-version" = "v1.34"
    })
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "kubernetes_resource_quota_v1" "lab" {
  for_each = local.namespaces
  metadata {
    name      = "lab-budget"
    namespace = kubernetes_namespace_v1.lab[each.key].metadata[0].name
    labels    = local.labels
  }
  spec {
    hard = {
      "requests.cpu"           = "2"
      "requests.memory"        = "2Gi"
      "limits.cpu"             = "4"
      "limits.memory"          = "4Gi"
      "pods"                   = "12"
      "persistentvolumeclaims" = "2"
      "requests.storage"       = "5Gi"
      "services.nodeports"     = "0"
      "services.loadbalancers" = "0"
    }
  }
}

resource "kubernetes_limit_range_v1" "lab" {
  for_each = local.namespaces
  metadata {
    name      = "container-defaults"
    namespace = kubernetes_namespace_v1.lab[each.key].metadata[0].name
    labels    = local.labels
  }
  spec {
    limit {
      type = "Container"
      default = {
        cpu    = "500m"
        memory = "256Mi"
      }
      default_request = {
        cpu    = "100m"
        memory = "64Mi"
      }
    }
  }
}

resource "kubernetes_role_v1" "observer" {
  for_each = local.namespaces
  metadata {
    name      = "lab-observer"
    namespace = kubernetes_namespace_v1.lab[each.key].metadata[0].name
    labels    = local.labels
  }
  rule {
    api_groups = [""]
    resources  = ["pods", "pods/log", "services", "events", "persistentvolumeclaims"]
    verbs      = ["get", "list", "watch"]
  }
  rule {
    api_groups = ["apps", "batch"]
    resources  = ["deployments", "statefulsets", "jobs"]
    verbs      = ["get", "list", "watch"]
  }
}

resource "kubernetes_role_binding_v1" "observer" {
  for_each = local.namespaces
  metadata {
    name      = "lab-observer"
    namespace = kubernetes_namespace_v1.lab[each.key].metadata[0].name
    labels    = local.labels
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.observer[each.key].metadata[0].name
  }
  subject {
    kind      = "Group"
    name      = "agentic-devops-observers"
    api_group = "rbac.authorization.k8s.io"
  }
}
