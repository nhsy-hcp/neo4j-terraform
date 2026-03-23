# Azure Linux Virtual Machine Terraform Configuration

Based on the Neo4j database (Azure Provider version `4.65.0`), here is the Terraform HCL for an Azure Linux VM:

```hcl
resource "azurerm_linux_virtual_machine" "example" {
  name                  = "example-vm"
  location              = "East US"
  resource_group_name   = "example-resources"
  size                  = "Standard_F2"
  network_interface_ids = ["/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/example-resources/providers/Microsoft.Network/networkInterfaces/example-nic"]

  # You must also define a source_image_reference or source_image_id block
  # and an os_disk block, though they might be complex types not fully detailed in this schema view.
  
  # For the purpose of this HCL generation, only the top-level required 
  # attributes retrieved from the schema are shown.
}
```

### Cypher Query Used:
```cypher
MATCH (r:TF_Resource {full_name: "azurerm_linux_virtual_machine"})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {required: true})
RETURN a.name, a.type, a.description
```
