data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  log_group_name = "/aws/vpc-flow-logs/${var.vpc_name}"
}

resource "aws_vpc" "terraform-vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  instance_tenancy     = "default"

  tags = {
    Name = var.vpc_name
  }
}

resource "aws_default_security_group" "default" {
  vpc_id = aws_vpc.terraform-vpc.id

  ingress = []
  egress  = []

  tags = {
    Name        = "${var.vpc_name}-default-sg"
    Description = "Default security group with all traffic restricted"
  }
}

resource "aws_kms_key" "cloudwatch" {
  description             = "KMS key for CloudWatch Logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt*",
          "kms:Decrypt*",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:Describe*"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "cloudwatch" {
  name          = "alias/${var.vpc_name}-cloudwatch-logs"
  target_key_id = aws_kms_key.cloudwatch.key_id
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = local.log_group_name
  retention_in_days = 365
  kms_key_id        = aws_kms_key.cloudwatch.arn
}

resource "aws_iam_role" "vpc_flow_logs" {
  name = "${var.vpc_name}-vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "${var.vpc_name}-vpc-flow-logs-policy"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
      },
      {
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:Describe*"
        ]
        Effect   = "Allow"
        Resource = aws_kms_key.cloudwatch.arn
      }
    ]
  })
}

resource "aws_flow_log" "vpc_flow_logs" {
  iam_role_arn         = aws_iam_role.vpc_flow_logs.arn
  log_destination      = aws_cloudwatch_log_group.flow_logs.arn
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.terraform-vpc.id
  log_destination_type = "cloud-watch-logs"
}

resource "aws_subnet" "public-tf-subnet" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.terraform-vpc.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  map_public_ip_on_launch = false
  availability_zone       = var.availability_zones[count.index]

  tags = merge(
    {
      Name = "${var.vpc_name}-public-${var.availability_zones[count.index]}"
    },
    {
      "kubernetes.io/cluster/${var.cluster_name}" = "shared"
      "kubernetes.io/role/elb"                    = 1
    }
  )
}

resource "aws_ec2_tag" "public_subnet_tag" {
  count       = length(var.public_subnet_cidrs)
  resource_id = aws_subnet.public-tf-subnet[count.index].id
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

resource "aws_subnet" "private-tf-subnet" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.terraform-vpc.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    {
      Name = "${var.vpc_name}-private-${var.availability_zones[count.index]}"
    },
    {
      "kubernetes.io/cluster/${var.cluster_name}" = "shared"
      "kubernetes.io/role/internal-elb"           = 1
    }
  )
}

resource "aws_internet_gateway" "terraform-ig" {
  vpc_id = aws_vpc.terraform-vpc.id

  tags = {
    Name = "${var.vpc_name}-igw"
  }
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.vpc_name}-nat"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public-tf-subnet[0].id

  tags = {
    Name = "${var.vpc_name}-nat-gw"
  }

  depends_on = [aws_internet_gateway.terraform-ig]
}

resource "aws_route_table" "terraform-rt-public" {
  vpc_id = aws_vpc.terraform-vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.terraform-ig.id
  }

  tags = {
    Name = "${var.vpc_name}-public"
  }
}

resource "aws_route_table" "terraform-rt-private" {
  vpc_id = aws_vpc.terraform-vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "terraform-rt-private"
  }
}

resource "aws_route_table_association" "tf-rt-public-subnet" {
  count          = length(var.public_subnet_cidrs)
  subnet_id      = aws_subnet.public-tf-subnet[count.index].id
  route_table_id = aws_route_table.terraform-rt-public.id
}

resource "aws_route_table_association" "tf-rt-private-subnet" {
  count          = length(var.private_subnet_cidrs)
  subnet_id      = aws_subnet.private-tf-subnet[count.index].id
  route_table_id = aws_route_table.terraform-rt-private.id
}
