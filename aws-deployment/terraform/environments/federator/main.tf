provider "aws" {
  region  = "us-east-2"
  version = "~> 2.44.0"
}

terraform {
  backend "s3" {
    bucket = "sov-devops-terraform"
    key    = "sov-terr-key"
    region = "us-east-2"
  }
}