terraform {
  required_providers {
    digitalocean = {
      source = "digitalocean/digitalocean"
      version = "~> 1.22.2"
    }
    local = {
      source = "hashicorp/local"
      version = "~> 1.4.0"
    }
    random = {
      source = "hashicorp/random"
      version = "~> 2.3.0"
    }
    template = {
      source = "hashicorp/template"
      version = "~> 2.1.2"
    }
  }
  required_version = ">= 0.13"
}

