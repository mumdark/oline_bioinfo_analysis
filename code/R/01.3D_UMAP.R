# main_script.R
library(Seurat)
library(dplyr)
library(scatterplot3d)
library(plotrix)
library(ggsci)  # 确保安装了 ggsci 包

analyze_data <- function(file_path, output_dir) {
  # 读入数据
  af <- readRDS(file_path)
  
  # 提取UMAP降维信息并绘图
  af <- RunUMAP(af, dims = 1:20, reduction = "pca", n.components = 3)
  af <- RunTSNE(af, dims = 1:20, reduction = "pca", n.components = 3)
  umap <- af@reductions$umap@cell.embeddings %>% as.data.frame()
  umap$Celltype <- af$Celltype %>% as.character()
  
  # 整理数据并可视化
  unique_celltypes <- unique(umap$Celltype)
  colors <- ggsci::pal_jco()(8)    # 指定颜色，可以自行修改
  color_map <- setNames(colors, unique_celltypes)
  data <- umap %>%
    mutate(Color = color_map[Celltype])
  
  # 生成 PDF 文件
  pdf_file_path <- file.path(output_dir, "scatterplot3d.pdf")
  pdf(file = pdf_file_path, width = 5, height = 5)
  par(mar = c(5, 4, 4, 10), xpd = TRUE)
  scatterplot3d(data[, 1:3], pch = ".", grid=FALSE, box=FALSE, color = data$Color, cex.symbol = 2)
  addgrids3d(data[, 1:3], grid = c("xy", "xz", "yz"))
  legend("topright", legend = levels(factor(data$Celltype)), col = unique(data$Color), pch = 16, inset = 0.02, horiz = FALSE, ncol = 2)
  dev.off()
  
  return(pdf_file_path)
}

# 允许从命令行运行
args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 1) {
  analyze_data(args[1], args[2])
}