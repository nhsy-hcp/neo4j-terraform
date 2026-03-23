resource "azurerm_linux_virtual_machine" "example" {
  location              = "East US"
  name                  = "example"
  network_interface_ids = ["nic-id"]
  resource_group_name   = "rg"
  size                  = "Standard_B1s"
}
