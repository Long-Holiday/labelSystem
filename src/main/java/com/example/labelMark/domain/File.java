package com.example.labelMark.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 * 
 * </p>
 *
 * @author wh
 * @since 2024-04-12
 */
@Getter
@Setter
@TableName("file")
@ApiModel(value = "File对象", description = "")
public class File implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableField("fileid")
    private Integer fileid;

    @TableField("filename")
    private String filename;

    @TableField("updatetime")
    private String updatetime;

    @TableField("status")
    private Integer status;

    @TableField("size")
    private String size;


}
